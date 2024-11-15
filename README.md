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

Go to example dir
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

`NotImplemented`

## Tracking jobs in Vertex AI

When using `python cellarium/workflows/submit_single_component.py` to submit a pipeline, a URL will be printed to stdout where you can track the progress of your pipeline using Vertex AI's web UI.
