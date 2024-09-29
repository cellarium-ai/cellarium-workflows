# Cellarium Workflows Example
This code contains helper functions and example to run scripts in Vertex AI platform (powered by Kubeflow)

## Quick start
* [Install gcloud CLI](https://cloud.google.com/sdk/docs/install)
* [Authenticate gcloud CLI util](https://cloud.google.com/docs/authentication/gcloud)
* Install project requirements like:
```bash
$ pip isntall -r requirements/base.txt
```

## Example
Go to example dir
```bash
$ cd cellarium/workflows/example
```
Submit an example pipeline:

```bash
$  python submit_example_pipeline.py --project_id dsp-cell-annotation-service --location us-central1 --display_name test --component_1_config gs://test-bucket/test-config-1.yaml --component_2_config gs://test-bucket/test-config-2.yaml 
```