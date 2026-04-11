# Nextflow pipelines for `cellarium-ml`

Nextflow pipelines for running [cellarium-ml](https://github.com/cellarium-ai/cellarium-ml) workflows at scale on Google Cloud Batch.

## The general idea

`cellarium-ml` can scale algorithms to handle large scRNA-seq datasets. This repository helps orchestrate the compute, and composes `cellarium-ml` models, hooking up outputs of one model to inputs of the next.

Here is an example. Run PCA on an arbitrarily large dataset (ideally created by Cellarium Nexus, but not necessarily) using google cloud hardware:

```bash
nextflow run pca.nf \
    --h5ad_bucket  'gs://my-bucket/data/extract_files' \
    --output_bucket 'gs://my-bucket/outputs/pca'
```

Includes highly-variable gene selection and gene z-scoring. Takes maybe 9 hours on 100M cells.  The output bucket will contain a trained PCA model checkpoint as well as the per-cell PCs in sharded CSV files.

## Pipelines

| Pipeline | File | Description |
|---|---|---|
| [PCA](cellarium/workflows/nextflow/README.md) | `cellarium/workflows/nextflow/pca.nf` | OnePass mean/var → HVG selection → Incremental PCA |

---

## Installing Nextflow

Nextflow requires Java 17 or later. The recommended install method is via [SDKMAN](https://sdkman.io/) or the standalone installer:

```bash
# Option A — standalone installer (macOS/Linux)
curl -s https://get.nextflow.io | bash
sudo mv nextflow /usr/local/bin/

# Option B — SDKMAN (manages Java too)
sdk install java 21-tem
curl -s https://get.nextflow.io | bash
```

Verify:

```bash
nextflow -version
```

You need at least **Nextflow 23.10** for the Google Batch executor used here.

---

## nf-google plugin

The `nf-google` plugin provides the Google Batch executor and GCS file staging — it is what lets Nextflow copy your `.h5ad` files from GCS onto each task VM without any `gcloud` CLI in your process container.

**You do not need to install it manually.** `nextflow.config` declares it:

```groovy
plugins {
    id 'nf-google'
}
```

On first run Nextflow downloads it automatically from [plugins.nextflow.io](https://plugins.nextflow.io) and caches it in `~/.nextflow/plugins/`. Subsequent runs are offline.

If you are in an air-gapped environment or want to pin a specific version:

```groovy
plugins {
    id 'nf-google@1.14.0'
}
```

---

## GCP prerequisites

Before running on Google Cloud Batch you need:

1. **APIs enabled** in your GCP project:
   ```bash
   gcloud services enable batch.googleapis.com storage.googleapis.com \
       artifactregistry.googleapis.com logging.googleapis.com
   ```

2. **A service account** (or your user account via ADC) with these roles:
   - `roles/batch.jobsEditor`
   - `roles/batch.agentReporter`
   - `roles/storage.objectAdmin` (on your work bucket and output bucket)
   - `roles/logging.logWriter`
   - `roles/artifactregistry.reader` (to pull the container image)

3. **Application Default Credentials** active on the machine where you run `nextflow`:
   ```bash
   gcloud auth application-default login
   ```

4. **A GCS work bucket** — Nextflow uses this for task staging and intermediate files. It must be in the same region as your Batch jobs (`us-central1` by default). Separate from your output bucket.
