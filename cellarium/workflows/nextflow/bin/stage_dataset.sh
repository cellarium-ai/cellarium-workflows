#!/usr/bin/env bash
# Stage an h5ad dataset for a task, optionally downloading it from GCS first.
# Usage: stage_dataset.sh <gcp_download> <dataset_dir> [smoke_test]
#
# <gcp_download>  "true"  – copy *.h5ad files from GCS to /tmp/dataset and
#                           print /tmp/dataset as the resolved path.
#                 "false" – print <dataset_dir> unchanged (no network I/O).
#
# [smoke_test]    "true"  – when gcp_download=true, download only the first
#                           10 files instead of the full dataset.
#                           (No effect when gcp_download=false.)
#
# The resolved dataset path is printed to stdout so callers can capture it:
#   _dataset_dir=$(stage_dataset.sh "${params.gcp_download}" "${dataset_dir}" "${params.smoke_test}")

set -euo pipefail

gcp_download="${1:-false}"
dataset_dir="${2:?Usage: stage_dataset.sh <gcp_download> <dataset_dir> [smoke_test]}"
smoke_test="${3:-false}"

if [ "$gcp_download" = "true" ]; then
    mkdir -p /tmp/dataset
    if [ "$smoke_test" = "true" ]; then
        echo "smoke_test=true: downloading first 10 .h5ad files from ${dataset_dir}" >&2
        gcloud storage ls "${dataset_dir}/*.h5ad" \
            | head -10 \
            | xargs -I{} gcloud storage cp {} /tmp/dataset/
    else
        gcloud storage cp "${dataset_dir}/*.h5ad" /tmp/dataset/
    fi
    echo /tmp/dataset
else
    # Streaming mode: pass GCS (or local) path through unchanged.
    # smoke_test is not supported in streaming mode (out of scope).
    echo "$dataset_dir"
fi
