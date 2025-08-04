"""Submit a multi-component cellarium-ml pipeline to Google Cloud Batch."""

import tempfile
import json
import yaml
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import click
from google.cloud import batch_v1

from shared_components import (
    get_current_google_user,
    get_allowed_cli_tool_names,
    create_batch_script,
    get_machine_type_resources,
)


def parse_pipeline_yaml(config: str) -> tuple[str, list[dict]]:
    """Parse pipeline YAML configuration - same as submit_pipeline.py"""
    with open(config) as f:
        config_contents = yaml.safe_load(f)
    top_level_keys = list(config_contents.keys())
    assert (
        len(top_level_keys) == 1
    ), "Pipeline YAML config error: The top level of the config file must be the display_name of the pipeline. Only one top level key is allowed."
    display_name = list(config_contents.keys())[0]
    component_definitions = config_contents[display_name]
    assert isinstance(
        component_definitions, list
    ), "Pipeline YAML config error: The value of the top level key must be a list of component definition dictionaries."
    for item in component_definitions:
        assert isinstance(
            item, dict
        ), "Pipeline YAML config error: Each component definition in the list must be a dictionary."
        assert (
            "tool" in item
        ), "Pipeline YAML config error: Each component definition must have a 'tool' key."
        assert (
            "subcommand" in item
        ), "Pipeline YAML config error: Each component definition must have a 'subcommand' key."
        assert (
            item["subcommand"] in ["fit", "predict"]
        ), "Pipeline YAML config error: The 'subcommand' key's value must be either 'fit' or 'predict'."
        assert (
            "config" in item
        ), "Pipeline YAML config error: Each component definition must have a 'config' key."
    return display_name, component_definitions


def create_batch_pipeline_jobs(
    pipeline_name: str,
    project: str,
    location: str,
    component_definitions: List[Dict[str, Any]],
    copy_data_to_local_disk: bool,
    base_image: str,
    git_sha: str = "",
    default_machine_type: str = "n1-standard-4",
    default_accelerator_type: str = "nvidia-tesla-t4",
    default_accelerator_count: int = 0,
    capture_logs_to_gcs: bool = False,
) -> List[batch_v1.Job]:
    """
    Create a list of Google Cloud Batch jobs for a pipeline.
    
    Note: Google Batch doesn't have built-in pipeline orchestration like Vertex AI,
    so we create individual jobs that can be submitted sequentially or managed externally.
    """
    jobs = []
    
    for i, component_def in enumerate(component_definitions):
        # Create unique job name with timestamp and UUID
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        job_name = f"{pipeline_name}-{i}-{component_def['tool']}-{component_def['subcommand']}-{timestamp}-{short_uuid}"
        job_name = job_name.lower().replace("_", "-")
        
        # Create batch script for this component using the shared function
        batch_script = create_batch_script(
            tool=component_def['tool'],
            subcommand=component_def['subcommand'],
            config=component_def['config'],
            git_sha=component_def.get('git_sha', git_sha),
            copy_data_to_local_disk=copy_data_to_local_disk,
            capture_logs_to_gcs=capture_logs_to_gcs,
        )

        # Create environment variables
        env_vars = {
            "TOOL": component_def['tool'],
            "SUBCOMMAND": component_def['subcommand'],
            "CONFIG": component_def['config'],
            "GIT_SHA": component_def.get('git_sha', git_sha),
            "COPY_DATA_TO_LOCAL_DISK": str(copy_data_to_local_disk).lower(),
            "CELLARIUM_CAPTURE_LOGS": str(capture_logs_to_gcs).lower(),
        }

        # Define the task specification
        task_spec = batch_v1.TaskSpec()
        
        # Configure the container runnable
        container = batch_v1.Runnable.Container()
        container.image_uri = base_image
        container.commands = ["/bin/bash", "-c", batch_script]
        
        # GPU access is automatically configured by Google Cloud Batch when GPUs are allocated
        if accelerator_count > 0:
            print(f"🔧 GPU access will be automatically configured by Google Cloud Batch for job {job_name}")
        
        runnable = batch_v1.Runnable()
        runnable.container = container
        
        # Set environment variables on the runnable
        runnable.environment = batch_v1.Environment()
        for key, value in env_vars.items():
            runnable.environment.variables[key] = value
        
        task_spec.runnables = [runnable]
        
        # Set compute resources based on machine type
        current_machine_type = component_def.get('machine_type', default_machine_type)
        cpu_milli, memory_mib = get_machine_type_resources(current_machine_type)
        compute_resource = batch_v1.ComputeResource()
        compute_resource.cpu_milli = cpu_milli
        compute_resource.memory_mib = memory_mib
        task_spec.compute_resource = compute_resource
        
        # Set maximum run duration
        max_duration = component_def.get('max_run_duration', '3600s')
        task_spec.max_run_duration = {"seconds": int(max_duration.rstrip("s"))}
        
        # Create task groups
        group = batch_v1.TaskGroup()
        group.task_count = 1
        group.task_spec = task_spec
        
        # Create allocation policy
        allocation_policy = batch_v1.AllocationPolicy()
        instance_policy = batch_v1.AllocationPolicy.InstancePolicy()
        instance_policy.machine_type = component_def.get('machine_type', default_machine_type)
        
        # Add GPU if specified
        accelerator_count = component_def.get('accelerator_count', default_accelerator_count)
        accelerator_type = component_def.get('accelerator_type', default_accelerator_type)
        
        if accelerator_count > 0 and accelerator_type:
            print(f"🔧 GPU Configuration for {job_name}:")
            print(f"   Type: {accelerator_type}")
            print(f"   Count: {accelerator_count}")
            print(f"   Formatted type: {accelerator_type.lower().replace('_', '-')}")
            
            # For Batch, GPUs are configured via accelerators in the instance policy
            accelerator = batch_v1.AllocationPolicy.Accelerator()
            accelerator.type_ = accelerator_type.lower().replace('_', '-')
            accelerator.count = accelerator_count
            instance_policy.accelerators = [accelerator]
            
            print(f"✅ Added GPU to job specification for {job_name}")
        else:
            print(f"❌ No GPU configured for {job_name} (count: {accelerator_count}, type: '{accelerator_type}')")
        
        instance_policy_or_template = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
        instance_policy_or_template.policy = instance_policy
        if accelerator_count > 0 and accelerator_type:
            instance_policy_or_template.install_gpu_drivers = True
        allocation_policy.instances = [instance_policy_or_template]
        
        # Create the job
        job = batch_v1.Job()
        job.task_groups = [group]
        job.allocation_policy = allocation_policy
        job.logs_policy = batch_v1.LogsPolicy()
        
        # Set log destination based on capture_logs_to_gcs setting
        if capture_logs_to_gcs:
            # When capturing logs to GCS, save logs to a local path and disable Cloud Logging
            # This significantly reduces Cloud Logging costs while still preserving logs in GCS
            job.logs_policy.destination = batch_v1.LogsPolicy.Destination.PATH
            job.logs_policy.logs_path = "/tmp/gcs_output/job_logs"
        else:
            # Default behavior - all logs go to Cloud Logging
            job.logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING
        
        jobs.append((job_name, job))
    
    return jobs


@click.command()
@click.option(
    "--config",
    required=True,
    help="Local path to the pipeline config YAML file.",
)
@click.option(
    "--copy-data-to-local-disk",
    default=True,
    type=bool,
    help="True copies GCS data to local disk fully (once) before training. False is ephemeral.",
)
@click.option(
    "--project",
    default="dsp-cell-annotation-service",
    help="Google Cloud project ID.",
)
@click.option(
    "--location",
    default="us-central1",
    help="Google Cloud location, e.g. 'us-central1'.",
)
@click.option(
    "--pipeline-name",
    default="",
    help="Pipeline name, defaults to f'{user}_{display_name}'.",
)
@click.option(
    "--git-sha",
    default="",
    type=str,
    help="Cellarium-ML git SHA to install (if provided).",
)
@click.option(
    "--base-image",
    default="us-central1-docker.pkg.dev/broad-dsde-methods/cellarium-ai/cellarium-ml:cellarium-gpt-cstorch",
    help="Base image for the component.",
)
@click.option(
    "--submit-sequentially",
    default=False,
    type=bool,
    help="Submit jobs one at a time (sequential) rather than all at once (parallel).",
)
@click.option(
    "--wait-between-jobs",
    default=0,
    type=int,
    help="Seconds to wait between job submissions when using --submit-sequentially.",
)
@click.option(
    "--default-machine-type",
    default="n1-standard-4",
    help="Default machine type for components that don't specify one.",
)
@click.option(
    "--default-accelerator-type",
    default="nvidia-tesla-t4",
    help="Default GPU type for components that don't specify one.",
)
@click.option(
    "--default-accelerator-count",
    default=0,
    type=int,
    help="Default number of GPUs for components that don't specify one.",
)
@click.option(
    "--capture-logs-to-gcs",
    default=False,
    is_flag=True,
    help="Capture stdout/stderr to files and sync to GCS instead of using Cloud Logging.",
)
def submit_batch_pipeline(
    project: str,
    location: str,
    config: str,
    copy_data_to_local_disk: bool,
    pipeline_name: str,
    git_sha: str,
    base_image: str,
    submit_sequentially: bool,
    wait_between_jobs: int,
    default_machine_type: str,
    default_accelerator_type: str,
    default_accelerator_count: int,
    capture_logs_to_gcs: bool,
):
    """
    Submit a multi-component cellarium-ml pipeline to Google Cloud Batch.
    
    Note: Unlike Vertex AI Pipelines, Google Batch doesn't have built-in 
    pipeline orchestration. This submits individual Batch jobs that can
    be run in parallel or sequentially.
    """
    # Parse the pipeline configuration
    display_name, component_definitions = parse_pipeline_yaml(config)
    
    # Set pipeline name
    if pipeline_name == "":
        user = get_current_google_user()
        base_name = f"{user}-{display_name}" if user else display_name
        
        # Add timestamp to ensure uniqueness (individual jobs will get their own UUIDs)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        pipeline_name = f"{base_name}-{timestamp}"
    else:
        # If user provided a custom pipeline name, still add timestamp to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        pipeline_name = f"{pipeline_name}-{timestamp}"
    
    pipeline_name = pipeline_name.lower().replace("_", "-")
    
    if (git_sha == "") and (len(base_image.split(":")[-1]) > 0):
        git_sha = base_image.split(":")[-1]
    
    print(f"Preparing pipeline '{pipeline_name}' with {len(component_definitions)} components...")
    print(f"Project: {project}")
    print(f"Location: {location}")
    print(f"Sequential submission: {submit_sequentially}")
    
    # Validate all tools
    url = f"https://raw.githubusercontent.com/cellarium-ai/cellarium-ml/{git_sha}/cellarium/ml/cli.py"
    cli_tool_names = get_allowed_cli_tool_names(url)
    if cli_tool_names is not None:
        for component_def in component_definitions:
            tool = component_def['tool']
            if tool not in cli_tool_names:
                raise ValueError(
                    f"Tool '{tool}' not found in allowed CLI tools at {url}.\n"
                    f"Allowed tool names:\n{cli_tool_names}"
                )
    
    # Create batch jobs
    batch_jobs = create_batch_pipeline_jobs(
        pipeline_name=pipeline_name,
        project=project,
        location=location,
        component_definitions=component_definitions,
        copy_data_to_local_disk=copy_data_to_local_disk,
        base_image=base_image,
        git_sha=git_sha,
        default_machine_type=default_machine_type,
        default_accelerator_type=default_accelerator_type,
        default_accelerator_count=default_accelerator_count,
        capture_logs_to_gcs=capture_logs_to_gcs,
    )
    
    # Submit jobs
    client = batch_v1.BatchServiceClient()
    parent = f"projects/{project}/locations/{location}"
    submitted_jobs = []
    
    print(f"\nSubmitting {len(batch_jobs)} jobs...")
    
    for i, (job_name, job_spec) in enumerate(batch_jobs):
        try:
            print(f"  Submitting job {i+1}/{len(batch_jobs)}: {job_name}")
            
            request = batch_v1.CreateJobRequest()
            request.parent = parent
            request.job_id = job_name
            request.job = job_spec
            
            operation = client.create_job(request=request)
            try:
                result = operation.result()
                submitted_jobs.append((job_name, result))
                print(f"    ✅ Job '{job_name}' submitted successfully (UID: {result.uid})")
            except AttributeError:
                # Handle case where operation.result() doesn't work as expected
                result = operation
                submitted_jobs.append((job_name, result))
                print(f"    ✅ Job '{job_name}' submitted successfully (Operation: {operation.name})")
                
                # Try to get the job details directly
                try:
                    job_resource = client.get_job(name=f"projects/{project}/locations/{location}/jobs/{job_name}")
                    submitted_jobs[-1] = (job_name, job_resource)  # Update with actual job
                    print(f"    Job UID: {job_resource.uid}")
                except Exception as e:
                    print(f"    Note: Could not fetch job details immediately: {e}")
            
            if submit_sequentially and i < len(batch_jobs) - 1 and wait_between_jobs > 0:
                import time
                print(f"    Waiting {wait_between_jobs} seconds before next job...")
                time.sleep(wait_between_jobs)
                
        except Exception as e:
            print(f"    ❌ Failed to submit job '{job_name}': {e}")
            if submit_sequentially:
                print("    Stopping sequential submission due to error.")
                break
            continue
    
    print(f"\n🎉 Pipeline submission complete!")
    print(f"Submitted {len(submitted_jobs)}/{len(batch_jobs)} jobs successfully.")
    
    if submitted_jobs:
        print("\nMonitoring commands:")
        print(f"  gcloud batch jobs list --location={location} --project={project}")
        for job_name, _ in submitted_jobs:
            print(f"  gcloud batch jobs describe {job_name} --location={location} --project={project}")
        
        print(f"\nView logs:")
        for job_name, _ in submitted_jobs:
            print(f"  gcloud logging read 'resource.type=\"gce_instance\" AND resource.labels.job_id=\"{job_name}\"' --project={project}")
    
    return submitted_jobs


if __name__ == "__main__":
    submit_batch_pipeline()
