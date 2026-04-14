#!/usr/bin/env bash
# Stage an h5ad dataset for a task, optionally downloading it from GCS first.
# Usage: stage_dataset.sh <gcp_download> <dataset_dir>
#
# <gcp_download>  "true"  – copy *.h5ad files from GCS to /tmp/dataset and
#                           print /tmp/dataset as the resolved path.
#                 "false" – print <dataset_dir> unchanged (no network I/O).
#
# The resolved dataset path is printed to stdout so callers can capture it:
#   _dataset_dir=$(stage_dataset.sh "${params.gcp_download}" "${dataset_dir}")

set -euo pipefail

gcp_download="${1:-false}"
dataset_dir="${2:?Usage: stage_dataset.sh <gcp_download> <dataset_dir>}"

if [ "$gcp_download" = "true" ]; then
    mkdir -p /tmp/dataset
    gcloud storage cp "${dataset_dir}/*.h5ad" /tmp/dataset/
    echo /tmp/dataset
else
    echo "$dataset_dir"
fi
