"""Submit a single component cellarium-ml job to Google Cloud Batch."""

import tempfile
import json
import uuid
from datetime import datetime
from pathlib import Path

import click
from google.cloud import batch_v1
from google.cloud import storage

from shared_components import (
    get_current_google_user,
    get_allowed_cli_tool_names,
    create_batch_script,
)


def create_batch_job_spec(
    job_name: str,
    project: str,
    location: str,
    tool: str,
    subcommand: str,
    config: str,
    git_sha: str,
    copy_data_to_local_disk: bool,
    base_image: str,
    machine_type: str = "n1-standard-4",
    accelerator_type: str = "nvidia-tesla-t4",
    accelerator_count: int = 1,
    max_run_duration: str = "3600s",
    capture_logs_to_gcs: bool = False,
) -> batch_v1.Job:
    """
    Create a Google Cloud Batch job specification.
    
    Args:
        job_name: Name of the batch job
        project: Google Cloud project ID
        location: Google Cloud location
        tool: Cellarium tool to run
        subcommand: Subcommand (fit/predict)
        config: Path to config file
        git_sha: Git SHA for cellarium-ml
        copy_data_to_local_disk: Whether to copy data locally
        base_image: Container image to use
        machine_type: Machine type for the job
        accelerator_type: GPU type
        accelerator_count: Number of GPUs
        max_run_duration: Maximum runtime in seconds format
        capture_logs_to_gcs: Capture stdout/stderr to files for GCS sync
    
    Returns:
        Google Cloud Batch job specification
    """
    
    # Create the batch script using the shared function
    batch_script = create_batch_script(
        tool=tool,
        subcommand=subcommand,
        config=config,
        git_sha=git_sha,
        copy_data_to_local_disk=copy_data_to_local_disk,
        capture_logs_to_gcs=capture_logs_to_gcs,
    )

    # Create environment variables for the container
    env_vars = {
        "TOOL": tool,
        "SUBCOMMAND": subcommand,
        "CONFIG": config,
        "GIT_SHA": git_sha,
        "COPY_DATA_TO_LOCAL_DISK": str(copy_data_to_local_disk).lower(),
        "CELLARIUM_CAPTURE_LOGS": str(capture_logs_to_gcs).lower(),
    }

    # Define the task specification
    task_spec = batch_v1.TaskSpec()
    
    # Configure the container runnable
    container = batch_v1.Runnable.Container()
    container.image_uri = base_image
    container.commands = ["/bin/bash", "-c", batch_script]
    
    # Add GPU-specific container options if GPUs are configured
    if accelerator_count > 0:
        # Enable GPU access for the container
        container.options = "--gpus=all"
        print(f"🔧 Configured container with GPU access: --gpus=all")
    
    runnable = batch_v1.Runnable()
    runnable.container = container
    
    # Set environment variables on the runnable
    runnable.environment = batch_v1.Environment()
    for key, value in env_vars.items():
        runnable.environment.variables[key] = value
    
    task_spec.runnables = [runnable]
    
    # Configure compute resources
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = 4000  # 4 CPUs worth of milliCPU
    resources.memory_mib = 16384  # 16 GB of memory
    task_spec.compute_resource = resources
    
    # GPU configuration goes in the allocation policy, not compute resources
    if accelerator_count > 0 and accelerator_type:
        print(f"Note: GPU configuration ({accelerator_count}x {accelerator_type}) will be set in allocation policy")
    
    # Set maximum run duration
    task_spec.max_run_duration = {"seconds": int(max_run_duration.rstrip("s"))}
    
    # Create task groups
    group = batch_v1.TaskGroup()
    group.task_count = 1
    group.task_spec = task_spec
    
    # Create allocation policy for machine type
    allocation_policy = batch_v1.AllocationPolicy()
    instance_policy = batch_v1.AllocationPolicy.InstancePolicy()
    instance_policy.machine_type = machine_type
    
    # Add GPU to instance policy if specified
    if accelerator_count > 0 and accelerator_type:
        print(f"🔧 GPU Configuration:")
        print(f"   Type: {accelerator_type}")
        print(f"   Count: {accelerator_count}")
        print(f"   Formatted type: {accelerator_type.lower().replace('_', '-')}")
        
        # For Batch, GPUs are configured via accelerators in the instance policy
        accelerator = batch_v1.AllocationPolicy.Accelerator()
        accelerator.type_ = accelerator_type.lower().replace('_', '-')
        accelerator.count = accelerator_count
        instance_policy.accelerators = [accelerator]
        
        print(f"✅ Added GPU to job specification")
    else:
        print(f"❌ No GPU configured (count: {accelerator_count}, type: '{accelerator_type}')")
    
    instance_policy_or_template = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
    instance_policy_or_template.policy = instance_policy
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
        print("📝 Logs will be saved to local files and synced to GCS (Cloud Logging disabled to save costs)")
    else:
        # Default behavior - all logs go to Cloud Logging
        job.logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING
        print("📝 Logs will be sent to Cloud Logging")
    
    return job


@click.command()
@click.option(
    "--tool",
    required=True,
    help="Tool to run, e.g. 'onepass_mean_var_std'.",
)
@click.option(
    "--subcommand",
    required=True,
    type=click.Choice(["fit", "predict"]),
    help="Subcommand to run, either 'fit' or 'predict'.",
)
@click.option(
    "--config",
    required=True,
    help="GCS path to the training config YAML file.",
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
    "--job-name",
    default="",
    help="Job name, defaults to f'{user}_{tool}_{subcommand}'.",
)
@click.option(
    "--machine-type",
    default="n1-standard-4",
    help="Machine type for the training job, e.g. 'n1-standard-4'.",
)
@click.option(
    "--accelerator-type",
    default="nvidia-tesla-t4",
    help="Type of accelerator (gpu), e.g. 'nvidia-tesla-t4'.",
)
@click.option(
    "--accelerator-count",
    default=1,
    type=int,
    help="Number of GPUs.",
)
@click.option(
    "--max-run-duration",
    default="3600s",
    help="Maximum runtime in seconds format, e.g. '3600s'.",
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
    "--capture-logs-to-gcs",
    default=False,
    is_flag=True,
    help="Capture stdout/stderr to files and sync to GCS instead of using Cloud Logging.",
)
def submit_batch_component(
    project: str,
    location: str,
    config: str,
    tool: str,
    subcommand: str,
    copy_data_to_local_disk: bool,
    job_name: str,
    machine_type: str,
    accelerator_type: str,
    accelerator_count: int,
    max_run_duration: str,
    git_sha: str,
    base_image: str,
    capture_logs_to_gcs: bool,
):
    """
    Submit a single component cellarium-ml job to Google Cloud Batch.
    """
    # Input validation and defaults
    if job_name == "":
        user = get_current_google_user()
        base_name = f"{user}-{tool}-{subcommand}" if user else f"{tool}-{subcommand}"
        
        # Add timestamp and short UUID to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        job_name = f"{base_name}-{timestamp}-{short_uuid}"
    else:
        # If user provided a custom job name, still add UUID to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        job_name = f"{job_name}-{timestamp}-{short_uuid}"
    
    # Ensure job name is valid for Batch (lowercase, hyphens only)
    job_name = job_name.lower().replace("_", "-")
    
    if (git_sha == "") and (len(base_image.split(":")[-1]) > 0):
        git_sha = base_image.split(":")[-1]
    
    # Validate tool name
    url = f"https://raw.githubusercontent.com/cellarium-ai/cellarium-ml/{git_sha}/cellarium/ml/cli.py"
    cli_tool_names = get_allowed_cli_tool_names(url)
    if cli_tool_names is not None:
        if tool not in cli_tool_names:
            raise ValueError(
                f"Tool '{tool}' not found in allowed CLI tools at {url}.\n"
                f"Allowed tool names:\n{cli_tool_names}"
            )
    
    # Handle GPU settings
    if accelerator_count == 0:
        accelerator_type = ""
        accelerator_count = 0
    
    print(f"Submitting job '{job_name}' to Google Cloud Batch...")
    print(f"Project: {project}")
    print(f"Location: {location}")
    print(f"Tool: {tool}")
    print(f"Subcommand: {subcommand}")
    print(f"Config: {config}")
    print(f"Machine type: {machine_type}")
    print(f"Accelerator: {accelerator_count}x {accelerator_type}" if accelerator_count > 0 else "No accelerator")
    print(f"Max runtime: {max_run_duration}")
    
    # Create the batch job specification
    job_spec = create_batch_job_spec(
        job_name=job_name,
        project=project,
        location=location,
        tool=tool,
        subcommand=subcommand,
        config=config,
        git_sha=git_sha,
        copy_data_to_local_disk=copy_data_to_local_disk,
        base_image=base_image,
        machine_type=machine_type,
        accelerator_type=accelerator_type,
        accelerator_count=accelerator_count,
        max_run_duration=max_run_duration,
        capture_logs_to_gcs=capture_logs_to_gcs,
    )
    
    # Submit the job
    client = batch_v1.BatchServiceClient()
    parent = f"projects/{project}/locations/{location}"
    
    try:
        request = batch_v1.CreateJobRequest()
        request.parent = parent
        request.job_id = job_name
        request.job = job_spec
        
        operation = client.create_job(request=request)
        print(f"Job creation operation: {operation.name}")
        
        # Wait for the operation to complete
        print("Waiting for job creation to complete...")
        try:
            result = operation.result()
            print(f"✅ Job '{job_name}' submitted successfully!")
            print(f"Job resource name: {result.name}")
            print(f"Job UID: {result.uid}")
            print(f"Job state: {result.status.state.name}")
        except AttributeError:
            # Handle case where operation.result() doesn't work as expected
            # The operation itself contains the job information
            result = operation
            print(f"✅ Job '{job_name}' submitted successfully!")
            print(f"Operation name: {operation.name}")
            
            # Try to get the job details directly
            try:
                job_resource = client.get_job(name=f"projects/{project}/locations/{location}/jobs/{job_name}")
                print(f"Job resource name: {job_resource.name}")
                print(f"Job UID: {job_resource.uid}")
                print(f"Job state: {job_resource.status.state.name}")
                result = job_resource
            except Exception as e:
                print(f"Note: Could not fetch job details immediately: {e}")
        
        # Print monitoring information
        print("\nMonitoring commands:")
        print(f"  gcloud batch jobs describe {job_name} --location={location} --project={project}")
        print(f"  gcloud batch jobs list --location={location} --project={project}")
        print(f"  gcloud logging read 'resource.type=\"gce_instance\" AND resource.labels.job_id=\"{job_name}\"' --project={project}")
        
        return result
        
    except Exception as e:
        print(f"❌ Failed to submit job: {e}")
        raise


if __name__ == "__main__":
    submit_batch_component()
