"""Cellarium CLI execution code for kubeflow components."""

from cellarium.ml.cli import main as cellarium_ml_cli
import gcsfs
import yaml
import re
import os
import sys
import contextlib
from datetime import datetime


def detect_gcs_paths_in_config(config_path: str):
    """Parse config file and detect GCS output paths."""
    gcs_paths = {}

    try:
        # Load the config file
        if config_path.startswith("gs://"):
            fs = gcsfs.GCSFileSystem()
            with fs.open(config_path, "r") as f:
                config_content = f.read()
        else:
            with open(config_path, "r") as f:
                config_content = f.read()

        # Find all /gcs/ paths in the config
        gcs_pattern = r"/gcs/([^/\s]+)(/[^\s]*)?"
        matches = re.findall(gcs_pattern, config_content)

        for bucket, path in matches:
            full_gcs_path = f"/gcs/{bucket}{path}"
            gcs_url = f"gs://{bucket}{path}"
            gcs_paths[full_gcs_path] = gcs_url

        return gcs_paths
    except Exception as e:
        print(f"Warning: Could not parse config for GCS paths: {e}")
        return {}


def setup_gcs_output_handling(config_path: str) -> str:
    """Main function to set up GCS output handling."""
    print("Setting up GCS output handling...")

    # Always create the job_logs directory for Batch logging
    # (even if CELLARIUM_CAPTURE_LOGS is false, Batch might write logs here)
    job_logs_dir = "/tmp/gcs_output/job_logs"
    os.makedirs(job_logs_dir, exist_ok=True)

    # Detect GCS paths in config
    gcs_paths = detect_gcs_paths_in_config(config_path)

    if not gcs_paths:
        print("No GCS output paths detected in config")
        return config_path

    print(f"Detected {len(gcs_paths)} GCS output paths:")
    for gcs_path, gcs_url in gcs_paths.items():
        print(f" {gcs_path} -> {gcs_url}")

    # Set up local directories and update config
    path_mapping = {}

    # Load the config
    if config_path.startswith("gs://"):
        fs = gcsfs.GCSFileSystem()
        with fs.open(config_path, "r") as f:
            config_content = f.read()
    else:
        with open(config_path, "r") as f:
            config_content = f.read()

    # Replace GCS paths with local paths
    updated_content = config_content
    for gcs_path, gcs_url in gcs_paths.items():
        # Create local directory
        local_path = f"/tmp/gcs_output{gcs_path[4:]}"  # Remove /gcs prefix
        os.makedirs(local_path, exist_ok=True)
        path_mapping[gcs_path] = local_path
        print(f"Mapped {gcs_path} -> {local_path} (will sync to {gcs_url})")

        # Update config content
        updated_content = updated_content.replace(gcs_path, local_path)

    # Write updated config to local file
    local_config_path = "/tmp/config_with_local_paths.yaml"
    with open(local_config_path, "w") as f:
        f.write(updated_content)

    # Store paths for later syncing
    with open("/tmp/gcs_sync_info.yaml", "w") as f:
        yaml.dump({"gcs_paths": gcs_paths, "path_mapping": path_mapping}, f)

    print(f"Updated config saved to {local_config_path}")
    return local_config_path


def setup_log_capture():
    """Set up stdout/stderr capture to files for later GCS sync."""
    # Create logs directory
    log_dir = "/tmp/gcs_output/job_logs"
    os.makedirs(log_dir, exist_ok=True)

    # Generate timestamped log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stdout_file = f"{log_dir}/stdout_{timestamp}.log"
    stderr_file = f"{log_dir}/stderr_{timestamp}.log"

    return stdout_file, stderr_file


@contextlib.contextmanager
def capture_logs_to_files(stdout_file, stderr_file):
    """Context manager to capture stdout/stderr to files while still showing output."""
    # Open log files
    stdout_log = open(stdout_file, "w")
    stderr_log = open(stderr_file, "w")

    class TeeWriter:
        def __init__(self, original, log_file):
            self.original = original
            self.log_file = log_file

        def write(self, text):
            self.original.write(text)
            self.log_file.write(text)
            self.original.flush()
            self.log_file.flush()

        def flush(self):
            self.original.flush()
            self.log_file.flush()

    # Save original stdout/stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        # Replace with tee writers
        sys.stdout = TeeWriter(original_stdout, stdout_log)
        sys.stderr = TeeWriter(original_stderr, stderr_log)
        yield stdout_file, stderr_file
    finally:
        # Restore original stdout/stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        stdout_log.close()
        stderr_log.close()


def finalize_gcs_output_sync():
    """Final step: sync all outputs back to GCS."""
    try:
        print("Finalizing GCS output sync...")

        # Load sync info
        if not os.path.exists("/tmp/gcs_sync_info.yaml"):
            print("No GCS sync info found")
            return

        with open("/tmp/gcs_sync_info.yaml", "r") as f:
            sync_info = yaml.safe_load(f)

        gcs_paths = sync_info.get("gcs_paths", {})
        path_mapping = sync_info.get("path_mapping", {})

        if not gcs_paths:
            print("No GCS paths to sync")
            return

        fs = gcsfs.GCSFileSystem()

        for gcs_path, gcs_url in gcs_paths.items():
            local_path = path_mapping.get(gcs_path)
            if not local_path or not os.path.exists(local_path):
                print(f"Skipping {gcs_path}: local path {local_path} not found")
                continue

            try:
                print(f"Syncing {local_path} to {gcs_url}")

                # Upload all files in the local directory
                for root, dirs, files in os.walk(local_path):
                    for file in files:
                        local_file = os.path.join(root, file)

                        # Calculate relative path and GCS destination
                        rel_path = os.path.relpath(local_file, local_path)
                        gcs_file = f"{gcs_url.rstrip('/')}/{rel_path}"

                        # Ensure parent directory exists in GCS
                        gcs_dir = "/".join(gcs_file.split("/")[:-1])
                        fs.makedirs(gcs_dir, exist_ok=True)

                        # Upload file
                        fs.put(local_file, gcs_file)
                        print(f" Uploaded {rel_path}")

                print(f" Successfully synced {local_path} to {gcs_url}")

            except Exception as e:
                print(f" Failed to sync {local_path} to {gcs_url}: {e}")

    except Exception as e:
        print(f"Warning: Could not finalize GCS sync: {e}")


# Set up GCS output handling before training
updated_config = setup_gcs_output_handling(config)  # noqa: F821

# Check if we should capture logs to files (for GCS sync)
capture_logs = os.environ.get("CELLARIUM_CAPTURE_LOGS", "").lower() == "true"

try:
    if capture_logs:
        # Set up log capture
        stdout_file, stderr_file = setup_log_capture()
        print(f" Capturing logs to {stdout_file} and {stderr_file}")

        # Run with log capture
        with capture_logs_to_files(stdout_file, stderr_file):
            cellarium_ml_cli(args=[tool, subcommand, "--config", updated_config])  # noqa: F821

        print(" Logs captured and will be synced to GCS")
    else:
        # Run normally without log capture
        cellarium_ml_cli(args=[tool, subcommand, "--config", updated_config])  # noqa: F821
finally:
    # Always try to sync outputs back to GCS
    finalize_gcs_output_sync()
