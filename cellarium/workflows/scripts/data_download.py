"""Data download and processing code for kubeflow components."""

import os
import glob
import gcsfs
import subprocess
from ruamel.yaml import YAML

# Get config from environment variable
config = os.environ.get("CONFIG")
if not config:
    raise RuntimeError("CONFIG environment variable not set")

# 0. localize the config file and set up local data directory
fs = gcsfs.GCSFileSystem()

# Create a dedicated directory for training data on local disk
# Prefer Local SSD if available for high-performance I/O
if os.path.exists("/mnt/disks/local-ssd"):
    LOCAL_DATA_DIR = "/mnt/disks/local-ssd/training_data"
    print(" Using Local SSD for high-performance data storage")
    print("df -h /mnt/disks/local-ssd:")
    subprocess.run(["df", "-h", "/mnt/disks/local-ssd"])
else:
    LOCAL_DATA_DIR = "/tmp/training_data"
    print(" Using boot disk for data storage")

os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
print(f" Created local data directory: {LOCAL_DATA_DIR}")


# Handle config file localization
if config.startswith("gs://"):
    print(f" Downloading config from GCS: {config}")
    # Use Local SSD for config if available, otherwise use /tmp
    if os.path.exists("/mnt/disks/local-ssd"):
        config_local_path = "/mnt/disks/local-ssd/downloaded_config.yaml"
    else:
        config_local_path = "/tmp/downloaded_config.yaml"

    with fs.open(config, "r") as fsrc:
        with open(config_local_path, "w") as fdst:
            fdst.write(fsrc.read())
    print(f" Config downloaded to: {config_local_path}")
else:
    print(f" Using local config: {config}")
    config_local_path = config

# 1. find data reference
yaml = YAML()
yaml.preserve_quotes = True

with open(config_local_path, "r") as f:
    config_data = yaml.load(f)
try:
    original_data_reference = config_data["data"]["dadc"]["init_args"]["filenames"]
except KeyError:
    raise RuntimeError(
        f"Could not find dataset in {config_local_path} when attempting to access data.dadc.init_args.filenames\n\n"
        f"{os.system('cat ' + config_local_path)}"
    )

# 2. download data to local disk
print(f"Copying data from GCS {original_data_reference} to local disk {LOCAL_DATA_DIR}")

sentinel_path = os.path.join(LOCAL_DATA_DIR, ".download_complete")
if os.path.exists(sentinel_path):
    print(f" Sentinel found at {sentinel_path} — data already downloaded, skipping.")
else:
    print(f" Downloading data via gsutil: {original_data_reference} -> {LOCAL_DATA_DIR}/")
    subprocess.run(
        f"gsutil -m cp {original_data_reference} {LOCAL_DATA_DIR}/",
        shell=True,
        executable="/bin/bash",
        check=True,
    )
    open(sentinel_path, "w").close()

print("Listing local .h5ad files (at most 10):")
h5ad_files = glob.glob(os.path.join(LOCAL_DATA_DIR, "*.h5ad"))
print("\n".join(h5ad_files[:10]))

# 3. rewrite the config file to point to the local data
if isinstance(original_data_reference, str):
    local_data_reference = os.path.join(
        LOCAL_DATA_DIR, os.path.basename(original_data_reference)
    )
else:
    local_data_reference = [
        os.path.join(LOCAL_DATA_DIR, os.path.basename(f))
        for f in original_data_reference
    ]
config_data["data"]["dadc"]["init_args"]["filenames"] = local_data_reference
with open(config_local_path, "w") as f:
    yaml.dump(config_data, f)
print(f"Re-writing config file {config_local_path} to point to local data:")
print(f" Data files now point to: {local_data_reference}")
print(" Config file contents:\n")
with open(config_local_path, "r") as f:
    print(f.read())

# Update the CONFIG environment variable to point to the local config file
# This ensures that cellarium_cli.py will use the updated config with local data paths
os.environ["CONFIG"] = config_local_path
print(f" Updated CONFIG environment variable to: {config_local_path}")
