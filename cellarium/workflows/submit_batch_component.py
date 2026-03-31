"""Submit a single component cellarium-ml job to Google Cloud Batch."""

import re
import textwrap
import uuid
from datetime import datetime

import click
from google.cloud import batch_v1

from .shared_components import (
    get_current_google_user,
    get_allowed_cli_tool_names,
    create_batch_script,
    get_machine_type_resources,
    extract_output_gcs_bucket_from_config,
    extract_data_gcs_bucket_from_config,
    extract_data_gcs_glob_from_config,
    assert_gcs_bucket_accessible_as_service_account,
    assert_data_first_file_exists,
    prepare_config_with_overrides,
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
    data_gcs_glob_uri: str = "",
    machine_type: str = "n1-standard-4",
    accelerator_type: str = "nvidia-tesla-t4",
    accelerator_count: int = 1,
    max_run_duration: str = "21600s",
    capture_logs_to_gcs: bool = False,
    output_gcs_bucket: str = None,
    local_ssd_size_gb: int = 375,
    network: str = "default-vpc",
    subnetwork: str = "",
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
        output_gcs_bucket: GCS destination for outputs (synced via rsync sidecar)
        local_ssd_size_gb: Size of Local SSD in GB (set to 0 to disable)
        network: VPC network name or full resource URL
        subnetwork: Subnet name or full resource URL (defaults to same name as network for AUTO-mode VPCs)

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
        output_gcs_bucket=output_gcs_bucket,
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

    # Pre-container Script runnable: runs directly on the VM host (not in Docker),
    # so gcloud uses the host's Python runtime with no container conflicts.
    # Downloads all data shards to the local SSD before the container starts,
    # then writes a sentinel file so data_download.py can skip the download step.
    task_spec_runnables = []
    if copy_data_to_local_disk and data_gcs_glob_uri:
        local_data_dir = (
            "/mnt/disks/local-ssd/training_data"
            if local_ssd_size_gb > 0
            else "/tmp/training_data"
        )
        sentinel_path = local_data_dir + "/.download_complete"
        data_download_script = textwrap.dedent(f"""
            #!/bin/bash
            set -e
            mkdir -p "{local_data_dir}"
            echo " Pre-container data download starting..."
            echo " Source: {data_gcs_glob_uri}"
            echo " Dest:   {local_data_dir}/"
            df -h "{local_data_dir}" || true
            gsutil -m cp {data_gcs_glob_uri} "{local_data_dir}/"
            touch "{sentinel_path}"
            echo " Download complete. Sentinel written to {sentinel_path}"
            df -h "{local_data_dir}"
        """).strip()

        pre_runnable = batch_v1.Runnable()
        pre_runnable.script = batch_v1.Runnable.Script()
        pre_runnable.script.text = data_download_script
        task_spec_runnables.append(pre_runnable)
        print(
            f" Added pre-container download runnable: gsutil -m cp {data_gcs_glob_uri} -> {local_data_dir}/"
        )

    # Resolve machine resources up front so shm-size can be derived from total RAM.
    cpu_milli, memory_mib = get_machine_type_resources(machine_type)

    # Configure the container runnable
    container = batch_v1.Runnable.Container()
    container.image_uri = base_image
    container.commands = ["/bin/bash", "-c", batch_script]

    # Configure shared memory for PyTorch DataLoader workers.
    # Use ~75% of total RAM so workers can buffer freely without crowding out
    # the training process.  Outside a container /dev/shm is unbounded, which
    # is why bus errors only appear when running containerised.
    shm_gb = max(1, (memory_mib * 3) // (1024 * 4))
    container.options = f"--shm-size={shm_gb}g"
    print(
        f" Configured container with shared memory size: {shm_gb}GB (~75% of {memory_mib // 1024}GB RAM)"
    )

    # GPU access is automatically configured by Google Cloud Batch when GPUs are allocated
    if accelerator_count > 0:
        print(" GPU access will be automatically configured by Google Cloud Batch")

    runnable = batch_v1.Runnable()
    runnable.container = container

    # Set environment variables on the runnable
    runnable.environment = batch_v1.Environment()
    for key, value in env_vars.items():
        runnable.environment.variables[key] = value

    task_spec_runnables.append(runnable)
    task_spec.runnables = task_spec_runnables

    # Task volumes (local SSD only — GCS sync is handled by the rsync sidecar in the batch script)
    task_volumes = []

    if output_gcs_bucket:
        print(
            f" GCS output destination: {output_gcs_bucket} (synced via rsync sidecar)"
        )
    else:
        print(" No GCS output bucket specified, outputs will remain on local disk")

    # Local SSD must be added as a Volume so Batch formats and mounts it into the container
    # at the specified mount_path before the container starts.
    if local_ssd_size_gb > 0:
        ssd_volume = batch_v1.Volume()
        ssd_volume.device_name = "local-ssd"  # must match attached_disk.device_name
        ssd_volume.mount_path = "/mnt/disks/local-ssd"
        ssd_volume.mount_options = ["rw,async"]
        task_volumes.append(ssd_volume)
        print(f" Local SSD configured: {local_ssd_size_gb}GB -> /mnt/disks/local-ssd")
    else:
        print(" Local SSD disabled, using boot disk only")

    # Set volumes on task spec
    if task_volumes:
        task_spec.volumes = task_volumes

    # Set compute resources based on machine type (already resolved above)
    compute_resource = batch_v1.ComputeResource()
    compute_resource.cpu_milli = cpu_milli
    compute_resource.memory_mib = memory_mib
    task_spec.compute_resource = compute_resource

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
        print(" GPU Configuration:")
        print(f" Type: {accelerator_type}")
        print(f" Count: {accelerator_count}")
        print(f" Formatted type: {accelerator_type.lower().replace('_', '-')}")

        # For Batch, GPUs are configured via accelerators in the instance policy
        accelerator = batch_v1.AllocationPolicy.Accelerator()
        accelerator.type_ = accelerator_type.lower().replace("_", "-")
        accelerator.count = accelerator_count
        instance_policy.accelerators = [accelerator]

        print(" Added GPU to job specification")
    else:
        print(
            f" No GPU configured (count: {accelerator_count}, type: '{accelerator_type}')"
        )

    # Add Local SSD configuration — must be done BEFORE assigning instance_policy to
    # instance_policy_or_template, because proto-plus copies the message on assignment;
    # any mutations to instance_policy after that point are silently ignored.
    if local_ssd_size_gb > 0:
        attached_disk = batch_v1.AllocationPolicy.AttachedDisk()
        attached_disk.new_disk = batch_v1.AllocationPolicy.Disk()
        attached_disk.new_disk.type_ = "local-ssd"
        attached_disk.new_disk.size_gb = local_ssd_size_gb
        attached_disk.device_name = "local-ssd"
        instance_policy.disks = [attached_disk]

    instance_policy_or_template = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
    instance_policy_or_template.policy = instance_policy
    if accelerator_count > 0 and accelerator_type:
        instance_policy_or_template.install_gpu_drivers = True

    allocation_policy.instances = [instance_policy_or_template]

    # Configure VPC network
    if network:
        # Build full resource URLs if short names were given
        net_url = (
            network
            if "/" in network
            else f"projects/{project}/global/networks/{network}"
        )
        # For AUTO-mode VPCs the subnet name matches the network name
        resolved_subnet = subnetwork or network
        sub_url = (
            resolved_subnet
            if "/" in resolved_subnet
            else f"projects/{project}/regions/{location}/subnetworks/{resolved_subnet}"
        )
        network_interface = batch_v1.AllocationPolicy.NetworkInterface()
        network_interface.network = net_url
        network_interface.subnetwork = sub_url
        network_policy = batch_v1.AllocationPolicy.NetworkPolicy()
        network_policy.network_interfaces = [network_interface]
        allocation_policy.network = network_policy
        print(f" Network: {net_url}")
        print(f" Subnetwork: {sub_url}")
    job = batch_v1.Job()
    job.task_groups = [group]
    job.allocation_policy = allocation_policy
    job.logs_policy = batch_v1.LogsPolicy()

    # Set log destination based on capture_logs_to_gcs setting
    if capture_logs_to_gcs:
        # Logs saved to local SSD (synced to GCS by the rsync sidecar) to avoid Cloud Logging costs
        if local_ssd_size_gb > 0:
            job.logs_policy.destination = batch_v1.LogsPolicy.Destination.PATH
            job.logs_policy.logs_path = "/mnt/disks/local-ssd/job_logs"
            print(
                " Logs will be saved to Local SSD and synced to GCS (Cloud Logging disabled to save costs)"
            )
        else:
            job.logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING
            print(
                " capture_logs_to_gcs requested but local_ssd_size_gb=0; falling back to Cloud Logging"
            )
    else:
        # Default behavior - all logs go to Cloud Logging
        job.logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING
        print(" Logs will be sent to Cloud Logging")

    return job


@click.command(short_help="Submit a single-component job to Google Cloud Batch.")
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
    default="dsp-cellarium",
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
    default="604800s",
    help="Maximum runtime in seconds format, max 7 days, e.g. '604800s'.",
)
@click.option(
    "--git-sha",
    default="main",
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
@click.option(
    "--local-ssd-size-gb",
    default=750,
    type=int,
    help="Size of Local SSD in GB in 375 increments (375, 750, 1125, etc.). Set to 0 to disable Local SSD.",
)
@click.option(
    "--dry-run",
    default=False,
    is_flag=True,
    help="Build and validate the job spec without submitting to Google Cloud Batch.",
)
@click.option(
    "--network",
    default="default",
    help="VPC network name or full resource URL. Defaults to 'default'.",
)
@click.option(
    "--subnetwork",
    default="",
    help="Subnet name or full resource URL. Defaults to the network name (valid for AUTO-mode VPCs).",
)
@click.option(
    "--extract-bucket",
    default=None,
    help="GCS URI prefix containing extract_*.h5ad files, e.g. gs://my-bucket/my-prefix. Overwrites config yaml paths.",
)
@click.option(
    "--staging-bucket",
    default=None,
    help="GCS URI prefix for staging local config files, e.g. gs://my-bucket/staging. Required when config is a local path and the config has no gs:// default_root_dir.",
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
    local_ssd_size_gb: int,
    dry_run: bool = False,
    network: str = "default-vpc",
    subnetwork: str = "",
    extract_bucket=None,
    staging_bucket=None,
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

    # Ensure job name is valid for Batch (lowercase, hyphens only, max 63 chars)
    job_name = job_name.lower().replace("_", "-")
    job_name = job_name[:63].rstrip("-")

    if not re.match(r"^\d+s$", max_run_duration):
        raise ValueError(
            f"max_run_duration must be in '<seconds>s' format, e.g. '3600s'. Got: '{max_run_duration}'"
        )

    if (git_sha == "") and (len(base_image.split(":")[-1]) > 0):
        git_sha = base_image.split(":")[-1]

    config = prepare_config_with_overrides(config, extract_bucket)

    # Auto-detect output GCS bucket from config (done early so it can be used for local config staging)
    output_gcs_bucket = extract_output_gcs_bucket_from_config(config)
    if output_gcs_bucket:
        print(f" Auto-detected output GCS bucket from config: {output_gcs_bucket}")
    else:
        print(" No GCS output bucket detected, using local storage only")

    # If config is a local path, upload it to GCS staging so the Batch VM can access it
    if not config.startswith("gs://"):
        bucket_for_staging = output_gcs_bucket or staging_bucket
        if not bucket_for_staging:
            raise ValueError(
                "Local config file provided but no GCS bucket is available for staging. "
                "Either add a gs:// default_root_dir to your config or pass "
                "--staging-bucket gs://my-bucket/path."
            )
        import gcsfs as _gcsfs

        fs = _gcsfs.GCSFileSystem()
        staged_config_path = (
            f"{bucket_for_staging.rstrip('/')}/staging/configs/{job_name}.yaml"
        )
        fs.put(config, staged_config_path)
        print(f" Uploaded local config to GCS staging: {staged_config_path}")
        config = staged_config_path

    # Pre-flight: check that the Batch SA can access the data bucket, and the first file exists
    data_bucket = extract_data_gcs_bucket_from_config(config)
    if data_bucket:
        assert_gcs_bucket_accessible_as_service_account(project, data_bucket)
        assert_data_first_file_exists(config)

    data_gcs_glob_uri = (
        extract_data_gcs_glob_from_config(config) if copy_data_to_local_disk else ""
    )

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
    print(
        f"Accelerator: {accelerator_count}x {accelerator_type}"
        if accelerator_count > 0
        else "No accelerator"
    )
    print(f"Max runtime: {max_run_duration}")
    print(f"Local SSD size: {local_ssd_size_gb}GB")

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
        data_gcs_glob_uri=data_gcs_glob_uri,
        machine_type=machine_type,
        accelerator_type=accelerator_type,
        accelerator_count=accelerator_count,
        max_run_duration=max_run_duration,
        capture_logs_to_gcs=capture_logs_to_gcs,
        output_gcs_bucket=output_gcs_bucket,
        local_ssd_size_gb=local_ssd_size_gb,
        network=network,
        subnetwork=subnetwork,
    )

    # Dry-run: validate and print job spec without submitting
    if dry_run:
        print(" Dry run: job spec built successfully, skipping submission.")
        print(job_spec)
        return

    # Submit the job
    client = batch_v1.BatchServiceClient()
    parent = f"projects/{project}/locations/{location}"

    try:
        request = batch_v1.CreateJobRequest()
        request.parent = parent
        request.job_id = job_name
        request.job = job_spec

        result = client.create_job(request=request)
        print(f" Job '{job_name}' submitted successfully!")
        print(f"Job resource name: {result.name}")
        print(f"Job UID: {result.uid}")
        print(f"Job state: {result.status.state.name}")

        # Print monitoring information
        print("\nMonitoring commands:")
        print(
            f" gcloud batch jobs describe {job_name} --location={location} --project={project}"
        )
        print(f" gcloud batch jobs list --location={location} --project={project}")
        print(
            f' gcloud logging read \'resource.type="gce_instance" AND resource.labels.job_id="{job_name}"\' --project={project}'
        )
        print(
            f"\nConsole URL:\n https://console.cloud.google.com/batch/jobs?project={project}"
        )

        return result

    except Exception as e:
        print(f" Failed to submit job: {e}")
        raise


if __name__ == "__main__":
    submit_batch_component()
