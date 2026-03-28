"""Data download and processing code for kubeflow components."""

import os
import concurrent.futures
import copy
import glob
import gcsfs
import re
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
else:
    LOCAL_DATA_DIR = "/tmp/training_data"
    print(" Using boot disk for data storage")

os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
print(f" Created local data directory: {LOCAL_DATA_DIR}")


def download_file(src):
    """Download a single file from GCS to local directory."""
    dst = os.path.join(LOCAL_DATA_DIR, os.path.basename(src))
    with fs.open(src, "rb") as fsrc:
        with open(dst, "wb") as fdst:
            fdst.write(fsrc.read())
    print(f"Copied {src} to {dst}")
    return dst


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
data_reference = copy.copy(original_data_reference)
if isinstance(data_reference, str):
    # Handle brace expansion
    if "{" in data_reference and ".." in data_reference:
        pattern = re.search(r"\{(\d+)\.\.(\d+)\}", data_reference)
        if pattern:
            start, end = map(int, pattern.groups())
            base_path = data_reference[: pattern.start()]
            suffix = data_reference[pattern.end() :]
            data_reference = [f"{base_path}{i}{suffix}" for i in range(start, end + 1)]
        else:
            data_reference = [data_reference]
    else:
        data_reference = [data_reference]

# Download files in parallel using gcsfs.get
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(download_file, src) for src in data_reference]
    downloaded_files = [
        future.result() for future in concurrent.futures.as_completed(futures)
    ]

print("Listing local .h5ad files:")
h5ad_files = glob.glob(os.path.join(LOCAL_DATA_DIR, "*.h5ad"))
print("\n".join(h5ad_files))

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
