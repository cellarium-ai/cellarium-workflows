# The workflows

- [PCA workflow](#pca-workflow-pca_workflownf) — full PCA training + prediction pipeline
- [HVG workflow](#hvg-workflow-hvg_workflownf) — standalone highly variable gene selection
- [Onepass workflow](#onepass-workflow-onepass_workflownf) — standalone mean/variance/std pass

`nextflow.config` (in this directory) is auto-detected by all workflows. Run with `-profile gcp` for Google Cloud Batch or `-profile local` for local execution via a conda environment.

---

# PCA workflow (`pca_workflow.nf`)

Runs a four-step [cellarium-ml](https://github.com/cellarium-ai/cellarium-ml) PCA training and prediction workflow on Google Cloud Batch.

See the [repo README](../../../README.md) for Nextflow installation, the nf-google plugin, and GCP prerequisites.

## DAG

```
ONEPASS_MEAN_VAR ──┐
                   ├──► INCREMENTAL_PCA ──► INCREMENTAL_PCA_PREDICT
HIGHLY_VARIABLE ───┘
     GENES
```

1. **`ONEPASS_MEAN_VAR`** — single pass over all cells to compute per-gene mean, variance, and std. Output: `onepass_mean_var_std.ckpt`. Runs in parallel with step 2.
2. **`HIGHLY_VARIABLE_GENES`** — selects HVGs (Seurat v3 flavor) per batch key. Output: `hvg.csv`. Runs in parallel with step 1.
3. **`INCREMENTAL_PCA`** — fits an incremental PCA model using ZScore normalization (from step 1) and HVG filtering (from step 2). Output: `pca_final.ckpt`.
4. **`INCREMENTAL_PCA_PREDICT`** — projects all cells through the trained PCA model. Output: `batch*.csv.gz`.

Config templates for each step live in `cellarium/workflows/configs/` as `.yaml.j2` files and are rendered at runtime with `bin/render_config.py`.

## Parameters

All parameters can be overridden on the command line with `--param value`.

**Infrastructure** (`nextflow.config`):

| Parameter | Default | Description |
|---|---|---|
| `google_project` | `dsp-cellarium` | GCP project ID |
| `google_region` | `us-central1` | Region for Batch jobs and GCS buckets |
| `work_bucket` | `gs://cellarium-dev-central/workflows/tmp` | GCS work dir for Nextflow staging |
| `spot` | `false` | Use preemptible VMs (`true` saves ~70%; evictions auto-retried) |
| `disk_size` | `750 GB` | pd-ssd disk per task VM |
| `container` | `cellarium-ml:0.0.8` | Container image for `-profile gcp` runs |

**Pipeline** (`pca_workflow.nf`):

| Parameter | Default | Description |
|---|---|---|
| `dataset_dir` | *(see pca_workflow.nf)* | GCS directory (or local path) of input `.h5ad` files |
| `outdir` | *(see pca_workflow.nf)* | GCS path (or local dir) where outputs are published |
| `n_components` | `64` | Number of PCA components |
| `n_top_genes` | `8000` | Number of highly variable genes to select |
| `flavor` | `seurat_v3` | HVG selection method |
| `batch_index_n` | `assay_suspension_type` | Obs column for batch-aware HVG selection; pass `''` to disable |

## Running on Google Cloud Batch

```bash
cd cellarium/workflows/nextflow

# Basic run — uses all defaults
nextflow run pca_workflow.nf -profile gcp

# Override dataset and output locations
nextflow run pca_workflow.nf -profile gcp \
    --dataset_dir 'gs://my-bucket/data/extract_files' \
    --outdir      'gs://my-bucket/outputs/pca_run_001'

# Run without batch correction (disables batch_index_n)
nextflow run pca_workflow.nf -profile gcp --batch_index_n ''

# Use spot VMs for lower cost (~70% savings; evictions auto-retried)
nextflow run pca_workflow.nf -profile gcp --spot true

# Use a larger disk for a bigger dataset
nextflow run pca_workflow.nf -profile gcp --disk_size '1500 GB'

# Resume a failed or interrupted run from where it left off
nextflow run pca_workflow.nf -profile gcp -resume
```

Nextflow prints a run name (e.g. `festive_curie`). Monitor progress:

```bash
# Live log
nextflow log festive_curie

# Poll until complete
watch -n 30 nextflow log festive_curie -f 'process,status,exit,duration'
```

Batch jobs are also visible in the [Google Cloud Batch console](https://console.cloud.google.com/batch/jobs).

## Running locally

Activate your cellarium conda environment first. Processes launched by Nextflow inherit the environment nextflow was launched from, so `render_config.py` and `cellarium-ml` are found automatically.

```bash
conda activate cellarium
cd cellarium/workflows/nextflow

nextflow run pca_workflow.nf -profile local \
    --dataset_dir /path/to/local/h5ad/dir \
    --outdir      ./local_outputs
```

---

# HVG workflow (`hvg_workflow.nf`)

Runs just the highly variable gene selection step in isolation. Useful for tuning HVG parameters independently before a full PCA run.

**`HIGHLY_VARIABLE_GENES`** — fits `HVGSeuratV3` over the dataset, computing per-gene variability scores per batch key. Output: a CSV of selected gene IDs published to `outdir/hvg_seurat_v3/`.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `dataset_dir` | *(see hvg_workflow.nf)* | Input `.h5ad` directory |
| `outdir` | *(see hvg_workflow.nf)* | Output directory |
| `n_top_genes` | `8000` | Number of HVGs to select |
| `flavor` | `seurat_v3` | HVG selection method |
| `batch_index_n` | `assay_suspension_type` | Obs column for batch-aware selection; pass `''` to disable |

## Running

```bash
cd cellarium/workflows/nextflow

# GCP
nextflow run hvg_workflow.nf -profile gcp \
    --dataset_dir 'gs://my-bucket/data/extract_files' \
    --outdir      'gs://my-bucket/outputs/hvg_run_001'

# Local
nextflow run hvg_workflow.nf -profile local \
    --dataset_dir /path/to/local/h5ad/dir \
    --outdir      ./local_outputs

# Disable batch correction
nextflow run hvg_workflow.nf -profile gcp --batch_index_n ''

# Try a different number of HVGs
nextflow run hvg_workflow.nf -profile gcp --n_top_genes 5000
```

---

# Onepass workflow (`onepass_workflow.nf`)

Runs just the mean/variance/std pass in isolation. Produces statistics used downstream by `INCREMENTAL_PCA` for ZScore normalization.

**`ONEPASS_MEAN_VAR`** — computes per-gene mean, variance, and std over all cells using `NormalizeTotal` → `Log1p` transforms. Output: `onepass_mean_var_std.ckpt` published to `outdir/onepass_mean_var_std/`.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `dataset_dir` | *(see onepass_workflow.nf)* | Input `.h5ad` directory |
| `outdir` | *(see onepass_workflow.nf)* | Output directory |

## Running

```bash
cd cellarium/workflows/nextflow

# GCP
nextflow run onepass_workflow.nf -profile gcp \
    --dataset_dir 'gs://my-bucket/data/extract_files' \
    --outdir      'gs://my-bucket/outputs/onepass_run_001'

# Local
nextflow run onepass_workflow.nf -profile local \
    --dataset_dir /path/to/local/h5ad/dir \
    --outdir      ./local_outputs
```

