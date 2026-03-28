# Google Cloud Batch Backend

This directory now supports three execution backends for cellarium-ml workflows:

## 1. Local Execution
```bash
python cellarium/workflows/local_single_component.py \
    --tool onepass_mean_var_std \
    --subcommand fit \
    --config /path/to/config.yaml
```

## 2. Vertex AI Pipelines
```bash
python cellarium/workflows/submit_single_component.py \
    --tool onepass_mean_var_std \
    --subcommand fit \
    --config gs://bucket/config.yaml \
    --project my-project \
    --location us-central1
```

## 3. Google Cloud Batch (NEW)
```bash
python cellarium/workflows/submit_batch_component.py \
    --tool onepass_mean_var_std \
    --subcommand fit \
    --config gs://bucket/config.yaml \
    --project my-project \
    --location us-central1 \
    --machine-type n1-standard-4 \
    --accelerator-type nvidia-tesla-v100 \
    --accelerator-count 1
```

## Google Cloud Batch Features

### Single Component Submission
- Direct container execution without Kubeflow overhead
- Simpler job management and monitoring
- Built-in logging to Cloud Logging
- Configurable machine types and resources

### Pipeline Submission
```bash
python cellarium/workflows/submit_batch_pipeline.py \
    --config pipeline_config.yaml \
    --project my-project \
    --location us-central1 \
    --submit-sequentially true \
    --default-machine-type n1-standard-8 \
    --default-accelerator-type nvidia-tesla-t4 \
    --default-accelerator-count 1
```

### Key Differences from Vertex AI

| Feature | Vertex AI Pipelines | Google Cloud Batch |
|---------|-------------------|-------------------|
| Orchestration | Built-in pipeline management | Manual job sequencing |
| Container overhead | Kubeflow components | Direct container execution |
| Monitoring | Vertex AI Console | Cloud Console + gcloud CLI |
| Cost | Higher (pipeline overhead) | Lower (direct compute) |
| Complexity | Higher | Lower |
| GCS Output | Automatic `/gcs/` mounting | Automatic detection and sync |

### Installation

Add to your environment:
```bash
pip install google-cloud-batch==0.17.36
```

### Authentication

```bash
gcloud auth application-default login
```

### Monitoring Jobs

```bash
# List jobs
gcloud batch jobs list --location=us-central1 --project=my-project

# Describe a specific job
gcloud batch jobs describe JOB_NAME --location=us-central1 --project=my-project

# View logs
gcloud logging read 'resource.type="gce_instance" AND resource.labels.job_id="JOB_NAME"' --project=my-project
```

### When to Use Which Backend

- **Local**: Development and testing
- **Vertex AI**: Complex pipelines with dependencies, need for visual monitoring
- **Google Batch**: Simple jobs, cost optimization, direct container execution

### Configuration

Batch jobs support the same configuration options as Vertex AI:
- `machine_type`: e.g., "e2-standard-4", "n1-standard-16", "n1-highmem-8"
- `accelerator_type`: e.g., "nvidia-tesla-t4", "nvidia-tesla-v100", "nvidia-tesla-k80"  
- `accelerator_count`: Number of GPUs (0 for CPU-only)
- `max_run_duration`: e.g., "3600s" (1 hour)
- `base_image`: Container image to use
- All standard cellarium-ml parameters

### Pipeline Configuration Example

You can specify different machine types and GPU configurations per component in your pipeline YAML:

```yaml
my_pipeline:
  - tool: data_preprocessing
    subcommand: fit
    config: gs://bucket/preprocess_config.yaml
    machine_type: e2-standard-8  # CPU-only for preprocessing
    
  - tool: model_training
    subcommand: fit  
    config: gs://bucket/train_config.yaml
    machine_type: n1-standard-4
    accelerator_type: nvidia-tesla-v100
    accelerator_count: 1
    max_run_duration: 7200s  # 2 hours
    
  - tool: model_inference
    subcommand: predict
    config: gs://bucket/predict_config.yaml
    machine_type: n1-highmem-16
    accelerator_type: nvidia-tesla-t4
    accelerator_count: 2
```

### GPU Support

GPU support is fully implemented! You can specify:

**Single Component:**
```bash
python cellarium/workflows/submit_batch_component.py \
    --tool my_gpu_tool \
    --subcommand fit \
    --config gs://bucket/config.yaml \
    --machine-type n1-standard-4 \
    --accelerator-type nvidia-tesla-v100 \
    --accelerator-count 1 \
    --max-run-duration 7200s
```

**Pipeline with Defaults:**
```bash
python cellarium/workflows/submit_batch_pipeline.py \
    --config pipeline.yaml \
    --default-machine-type n1-standard-8 \
    --default-accelerator-type nvidia-tesla-t4 \
    --default-accelerator-count 1
```

**Supported GPU Types:**
- `nvidia-tesla-k80`
- `nvidia-tesla-p4` 
- `nvidia-tesla-p100`
- `nvidia-tesla-v100`
- `nvidia-tesla-t4`
- `nvidia-tesla-a100` (where available)

Components without explicit GPU configuration will use the defaults (CPU-only for single components, or pipeline defaults for pipelines).

## GCS Output Handling

**Your existing configs work seamlessly!** The Batch implementation automatically handles `/gcs/` paths in your configuration files.

### How It Works

1. **Detection**: The system scans your config file for any `/gcs/bucket/path` references
2. **Local Mapping**: Creates corresponding local directories like `/tmp/gcs_output/bucket/path`
3. **Config Update**: Temporarily updates your config to use local paths during training
4. **Automatic Sync**: After training completes, syncs all outputs back to the original GCS locations

### Example

Your existing config:
```yaml
trainer:
  default_root_dir: /gcs/my-bucket/models/experiment_1/
  max_epochs: 100
callbacks:
  checkpoint:
    dirpath: /gcs/my-bucket/checkpoints/
```

During execution:
1. Local directories created: `/tmp/gcs_output/my-bucket/models/experiment_1/`
2. Training runs with local paths (fast I/O)
3. After completion: all outputs synced to `gs://my-bucket/models/experiment_1/`

### Logging and Outputs

**Works automatically** - no code changes needed:
- Model checkpoints → synced to GCS
- Training logs → synced to GCS  
- TensorBoard logs → synced to GCS
- Any other outputs in `/gcs/` paths → synced to GCS

**Output appears in Cloud Logging too:**
```bash
# View job logs
gcloud logging read 'resource.type="gce_instance" AND resource.labels.job_id="JOB_NAME"' --project=my-project
```

### Log Capture to GCS

You can optionally capture stdout/stderr to files and sync them to GCS instead of relying only on Cloud Logging:

**Single Component:**
```bash
python cellarium/workflows/submit_batch_component.py \
    --tool scvi \
    --subcommand fit \
    --config scvi_train_config.yaml \
    --machine-type n1-standard-4 \
    --accelerator-type nvidia-tesla-t4 \
    --accelerator-count 1 \
    --capture-logs-to-gcs
```

**Pipeline:**
```bash
python cellarium/workflows/submit_batch_pipeline.py \
    --config pipeline_config.yaml \
    --capture-logs-to-gcs
```

**What happens with `--capture-logs-to-gcs`:**
1. `LogsPolicy.destination = PATH` (instead of CLOUD_LOGGING)  
2. `LogsPolicy.logs_path = /tmp/gcs_output/job_logs`
3. Batch writes logs directly to local files (bypassing Cloud Logging)
4. stdout/stderr are also captured by our script to timestamped files
5. All logs get synced to GCS automatically
6. **Major cost savings**: No Cloud Logging ingestion charges!

**Cost Savings Example:**
- Job with 10GB of logs:
  - Cloud Logging: $5.00 ingestion + $0.10/month storage = **$5.10**
  - GCS Storage: $0.20/month storage = **$0.20**  
  - **Savings: $4.90 per job (96% reduction!)**

**Final GCS structure includes:**
```
gs://your-bucket/path/to/output/
├── model_checkpoints/
├── lightning_logs/
└── job_logs/
    ├── stdout_20250803_143022.log
    └── stderr_20250803_143022.log
```

**Benefits:**
- Complete job logs archived in GCS alongside other outputs
- No dependency on Cloud Logging retention policies
- Easy to download and analyze logs locally
- Works with existing GCS output handling

### Benefits

- **Same configs work everywhere**: Local, Vertex AI, and Batch
- **Faster training**: Local I/O during training, GCS sync after
- **Automatic delocalization**: No manual file copying needed
- **Reliable**: Robust error handling and retry logic
