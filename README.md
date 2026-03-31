# Cellarium Workflows

A CLI tool for submitting [cellarium-ml](https://github.com/cellarium-ai/cellarium-ml) training and inference jobs to different compute backends.

Example: start an scVI run on the entire 20250811 CZI cellxgene census on specified Google Compute Engine hardware, all from your command line:

```bash
cellarium-workflow submit-batch-component \
    --tool scvi \
    --subcommand fit \
    --config folder/scvi_config.yaml \
    --machine-type n1-standard-16 \
    --accelerator-type nvidia-tesla-t4 \
    --accelerator-count 1 \
    --extract-bucket gs://bucket/path/to/extract_files
```

In this example, `gs://bucket/path/to/extract_files` is the bucket created by extracting data using `Cellarium Nexus`.  If data or configs or output directories in the config file are in Google Cloud Storage, file localization will be handled automatically.

## Installation

```bash
pip install -e .
```

This installs the `cellarium-workflow` command.

## Backends

The best tested method is `submit-batch-component`, and we recommend it for most use cases.

| Sub-command | Where it runs |
|---|---|
| `local-single-component` | Local machine |
| `submit-vertex-component` | Vertex AI Pipelines (single step) |
| `submit-vertex-pipeline` | Vertex AI Pipelines (sequential multi-step) |
| `submit-batch-component` | Google Cloud Batch (single job) |
| `submit-batch-pipeline` | Google Cloud Batch (sequential multi-step) |

## Usage

### Local

Run a job on your local machine — useful for development and smoke-testing.

```bash
cellarium-workflow local-single-component \
    --tool onepass_mean_var_std \
    --subcommand fit \
    --config /path/to/config.yaml
```

### Vertex AI — Single Component

Submit a single job to Vertex AI Pipelines.

```bash
cellarium-workflow submit-vertex-component \
    --tool onepass_mean_var_std \
    --subcommand fit \
    --config gs://bucket/config.yaml \
    --project my-project \
    --machine-type n1-standard-8 \
    --accelerator-type NVIDIA_TESLA_T4 \
    --accelerator-count 1
```

### Vertex AI — Pipeline

Submit a multi-step sequential pipeline to Vertex AI.

```bash
cellarium-workflow submit-vertex-pipeline \
    --pipeline-config pipeline_config.yaml \
    --project my-project
```

### Google Cloud Batch — Single Component

Submit a single job to Cloud Batch. Supports local SSD data staging, custom networking, and optional log capture to GCS.

```bash
cellarium-workflow submit-batch-component \
    --tool scvi \
    --subcommand fit \
    --config gs://bucket/config.yaml \
    --project my-project \
    --machine-type n1-standard-4 \
    --accelerator-type nvidia-tesla-t4 \
    --accelerator-count 1
```

### Google Cloud Batch — Pipeline

Submit a multi-step pipeline as individual Cloud Batch jobs. Use `--submit-sequentially` to run them one at a time.

```bash
cellarium-workflow submit-batch-pipeline \
    --config pipeline_config.yaml \
    --project my-project \
    --submit-sequentially true
```

## Configuration

### Training Config

A standard [PyTorch Lightning CLI](https://lightning.ai/docs/pytorch/stable/cli/lightning_cli.html) YAML. The key fields used by this tool are:

```yaml
trainer:
  default_root_dir: gs://my-bucket/outputs/
data:
  dadc:
    class_path: cellarium.ml.data.DistributedAnnDataCollection
    init_args:
      filenames: gs://bucket/path/extract_{0..9446}.h5ad
      shard_size: 10000
      last_shard_size: 3147
```

The `filenames` field uses brace-expansion to reference sharded `.h5ad` files. You can pass `--extract-bucket gs://bucket/path/` to have the tool auto-populate `filenames`, `shard_size`, and `last_shard_size` from GCS at submission time instead of hardcoding them.

### Pipeline Config

A YAML file listing the steps to run in order:

```yaml
my_pipeline_name:
  - tool: onepass_mean_var_std
    subcommand: fit
    config: gs://bucket/configs/onepass_config.yaml
    machine_type: n1-standard-4
    accelerator_type: nvidia-tesla-t4
    accelerator_count: 1

  - tool: scvi
    subcommand: fit
    config: gs://bucket/configs/scvi_config.yaml
    machine_type: n1-standard-16
    accelerator_type: nvidia-tesla-v100
    accelerator_count: 1
    max_run_duration: 7200s
```

Each step can specify its own machine type and GPU configuration. Fields not set on a step inherit the pipeline defaults.

## Authentication

```bash
gcloud auth application-default login
```

## Google Batch setup

For a new Google project which has never used Batch before, you will need to set up a few things. We have distilled this into a helper script, included here.  Fill in `PROJECT_ID` with the appropriate value for your Google project.

```bash
#!/bin/bash

# =======================================================================
# Set your Google Cloud Project ID here
# =======================================================================
PROJECT_ID="your-project-id-here"

echo "Starting Google Batch setup for project: $PROJECT_ID..."

# 1. Enable the Google Batch API (and Compute Engine API, which is a prerequisite)
echo "Enabling necessary APIs..."
gcloud services enable batch.googleapis.com compute.googleapis.com \
    --project="$PROJECT_ID"

# 2. Create a "default" VPC network 
# (An auto-mode network automatically creates subnets in all regions, including us-central1)
echo "Creating 'default' VPC network..."
gcloud compute networks create default \
    --subnet-mode=auto \
    --project="$PROJECT_ID" || true

# 3. Turn on Private Google Access for the us-central1 subnet
echo "Enabling Private Google Access for us-central1..."
gcloud compute networks subnets update default \
    --region=us-central1 \
    --enable-private-ip-google-access \
    --project="$PROJECT_ID"

# 4. Create an egress firewall rule for the Batch Agent
# This ensures the VM can reach out to Google APIs on port 443 even if standard egress is blocked
echo "Creating egress firewall rule for TCP 443..."
gcloud compute firewall-rules create allow-batch-agent-egress \
    --network=default \
    --direction=EGRESS \
    --action=ALLOW \
    --destination-ranges=0.0.0.0/0 \
    --rules=tcp:443 \
    --description="Allows Google Batch agent to communicate with Google APIs" \
    --project="$PROJECT_ID" || true

# 5. Find the Compute Engine default service account
echo "Locating the Compute Engine default service account..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo "Found Service Account: $COMPUTE_SA"

# 6. Grant the required IAM permissions to the service account
echo "Applying IAM roles..."

# Batch Agent Reporter (Critical for the VM to report status)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$COMPUTE_SA" \
    --role="roles/batch.agentReporter" \
    --condition=None > /dev/null

# Logs Writer (Critical for stdout/stderr logs from the container)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$COMPUTE_SA" \
    --role="roles/logging.logWriter" \
    --condition=None > /dev/null

# Storage Object Admin (Critical for mounting GCS buckets)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$COMPUTE_SA" \
    --role="roles/storage.objectAdmin" \
    --condition=None > /dev/null

echo "Setup complete! The project $PROJECT_ID is ready for Google Batch."
```
