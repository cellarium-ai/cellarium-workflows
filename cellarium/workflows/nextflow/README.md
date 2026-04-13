# The workflows

% link to the other headings like a table of contents

# PCA workflow (`pca_workflow.nf`)

Runs a three-step [cellarium-ml](https://github.com/cellarium-ai/cellarium-ml) PCA workflow on Google Cloud Batch.

See the [repo README](../../../README.md) for Nextflow installation, the nf-google plugin, and GCP prerequisites.

## DAG

```
ONEPASS_MEAN_VAR ──┐
                   ├──► INCREMENTAL_PCA
HIGHLY_VARIABLE ───┘
     GENES
```

1. **`ONEPASS_MEAN_VAR`** — single pass over all cells to compute per-gene mean, variance, and std. Output: `onepass_mean_var_std.ckpt`.
2. **`HIGHLY_VARIABLE_GENES`** — selects 8,000 HVGs (Seurat v3 flavor) per batch key. Output: `hvg.csv`. Runs in parallel with step 1.
3. **`INCREMENTAL_PCA`** — fits a 64-component PCA using ZScore normalization (from step 1) and HVG filtering (from step 2). Output: `pca_final.ckpt`.

Config files for each step live in `cellarium/workflows/configs/` and are staged to each task VM automatically by Nextflow.

---

## Configuration

`nextflow.config` lives next to `pca.nf` and is picked up automatically. Key parameters you will want to set — either by editing the file or overriding on the command line with `--param value`:

| Parameter | Default | Description |
|---|---|---|
| `google_project` | `broad-dsde-methods` | GCP project ID |
| `google_region` | `us-central1` | Region for Batch jobs and GCS buckets |
| `work_bucket` | `gs://cellarium-dev-central/workflows/tmp` | GCS path for Nextflow work dir |
| `spot` | `false` | Use preemptible VMs (`true` saves ~70%; retries on eviction) |
| `disk_size` | `750 GB` | pd-ssd disk per task (increase if staging > ~500 GB) |

Pipeline-specific parameters (in `pca.nf`):

| Parameter | Default | Description |
|---|---|---|
| `h5ad_bucket` | *(see pca.nf)* | GCS directory containing input `.h5ad` files |
| `output_bucket` | *(see pca.nf)* | GCS path where final outputs are published |
| `container` | `cellarium-ml:0.0.8` | Container image (Artifact Registry) |

---

## Running on Google Cloud Batch

```bash
cd cellarium/workflows/nextflow

# Override input/output buckets
nextflow run pca.nf \
    --h5ad_bucket  'gs://my-bucket/data/extract_files' \
    --output_bucket 'gs://my-bucket/outputs/pca'

# Use spot VMs for lower cost (~70% savings; evictions auto-retried)
nextflow run pca.nf --spot true

# Different disk size (e.g. for a larger dataset)
nextflow run pca.nf --disk_size '1500 GB'

# Resume a failed/interrupted run from where it left off
nextflow run pca.nf -resume
```

Nextflow prints a run name (e.g. `festive_curie`). Monitor progress:

```bash
# Live log
nextflow log festive_curie

# Poll until complete
watch -n 30 nextflow log festive_curie -f 'process,status,exit,duration'
```

Batch jobs are also visible in the [Google Cloud Batch console](https://console.cloud.google.com/batch/jobs).

---

## Running locally

For local runs (e.g. testing on a small subset), override the executor to bypass Google Batch entirely. Nextflow will run each process as a local subprocess using Docker.

Ensure Docker is running, then:

```bash
cd cellarium/workflows/nextflow

nextflow run pca.nf \
    -process.executor='local' \
    --h5ad_bucket /path/to/local/h5ad/dir \
    --output_bucket ./local_outputs
```

# HVG workflow


