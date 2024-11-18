# Cellarium Workflows

This package contains a command line tool to submit cellarium-ml pipelines to the Vertex AI platform (powered by Kubeflow).

## Installation

* [Install gcloud CLI](https://cloud.google.com/sdk/docs/install)
* [Authenticate gcloud CLI util](https://cloud.google.com/docs/authentication/gcloud)
* Set up [conda environment](https://docs.anaconda.com/miniconda/#quick-command-line-install) for pipeline submissions and install this package. Run the following commands:
```bash
  (base) $  git clone https://github.com/cellarium-ai/cellarium-workflows.git
  (base) $  cd cellarium-workflows
  (base) $  conda create -n vertex python=3.10
  (base) $  conda activate vertex
(vertex) $  pip install .
```

## Example

This is a fully working example that will run a smoke test of `cellarium-ml onepass_mean_var_std fit -c cellarium/workflows/example/onepass_train_smoketest_config.yaml` on Vertex AI Pipelines.

Go to the example directory and run the script:

```bash
(vertex) $  cd cellarium/workflows/example
(vertex) $  ./onepass_train_smoketest.sh
```

The bash script copies a local YAML file to the cloud and then runs the command line tool to submit a pipeline. See the contents of `cellarium/workflows/example/onepass_train_smoketest.sh` for details.

## Quick start

No changes to the code in this repo are necessary. Simply run the appropriate command line tool with the appropriate input arguments.

### Pipeline consisting of one component

1. Create a YAML config file for the `cellarium-ml` tool you wish to run.
2. Copy the YAML config file to a google bucket like `gs://bucket/path/to/config.yaml`
3. Run the following from the command line to submit a pipeline:

```bash
(vertex) $  python cellarium/workflows/submit_single_component.py \
                --tool onepass_mean_var_std \
                --subcommand fit \
                --config gs://bucket/path/to/onepass_config.yaml
```

That's it!

#### Additional input arguments

You might want to specify a few more optional inputs, for example:

```bash
(vertex) $  python cellarium/workflows/submit_single_component.py \
                --tool scvi \
                --subcommand fit \
                --config gs://bucket/path/to/scvi_config.yaml \
                --accelerator-type NVIDIA_TESLA_T4 \
                --accelerator-count 2 \
                --git-sha ffa12699f0ae9951454f77cd3151961a0693f365
```

Run this to see more information about optional inputs:

```bash
(vertex) $  python cellarium/workflows/submit_single_component.py --help
```

### Sequential pipeline consisting of several components

1. Decide which `cellarium-ml` tools will be run in which order.
2. Create YAML config files for each `cellarium-ml` tool you wish to run.
3. Copy the YAML config files to a google bucket like `gs://bucket/path/to/config1.yaml`, `gs://bucket/path/to/config2.yaml`, etc.
4. Create a pipeline YAML config file (this "pipeline config" file is something different than a `cellarium-ml` config file). This can be a local file, and does not need to be in a google bucket. Here is an example pipeline YAML config file that runs `onepass_mean_var_std`, `incremental_pca`, and `logistic_regression` in that order:

```yaml
example_pipeline_name:
  - tool: onepass_mean_var_std
    subcommand: fit
    config: gs://bucket/path/to/onepass_train_config.yaml
    machine_type: n1-standard-4
    accelerator_count: 0
  - tool: incremental_pca
    subcommand: fit
    config: gs://bucket/path/to/incremental_pca_train_config.yaml
    machine_type: n1-standard-16
    accelerator_type: nvidia-t4
    accelerator_count: 4
  - tool: logistic_regression
    subcommand: fit
    config: gs://bucket/path/to/logistic_regression_train_config.yaml
    machine_type: n1-standard-16
    accelerator_type: nvidia-t4
    accelerator_count: 4
```

5. Run the following from the command line to submit the pipeline (the example `pipeline_config.yaml` in this repository just runs `onepass_mean_var_std` twice):

```bash
(vertex) $  python cellarium/workflows/submit_pipeline.py \
                --pipeline-config cellarium/workflows/example/pipeline_config.yaml
```

NOTE: It is also possible to run a single component pipeline using a pipeline config file, rather than using `python submit_single_component.py` as above. Simply specify a pipeline YAML config with a single element list, like this:

```yaml
my_single_component_pipeline:
  - tool: onepass_mean_var_std
    subcommand: fit
    config: gs://bucket/path/to/onepass_train_config.yaml
    machine_type: n1-standard-4
    accelerator_count: 0
```

## Tracking jobs in Vertex AI

When a pipeline has been submitted using one of the above options, a URL will be printed to stdout where you can track the progress of your pipeline using Vertex AI's web UI.
