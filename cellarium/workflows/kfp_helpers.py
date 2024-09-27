import tempfile
import typing as t
import os

from kfp import compiler
from kfp.components import BaseComponent
from google.cloud import aiplatform
from google_cloud_pipeline_components.v1.custom_job import create_custom_training_job_from_component


def create_job(
    component_func: t.Callable[..., t.Any],
    config: str,
    display_name: str = "",
    replica_count: int = 1,
    machine_type: str = "n1-standard-4",
    accelerator_type: str = "",
    accelerator_count: int = 1,
    boot_disk_size_gb: int = 100
) -> t.Callable[[], t.Any]:
    """
    Create a custom training Google Vertex AI job for running a custom training component.

    :param component_func: Custom training component.
    :param config: Config file path on GCS.
    :param display_name: Display name of component in Vertex AI
    :param replica_count: The count of instances in the cluster.
    :param machine_type: The type of the machine to run the CustomJob.
    :param accelerator_type: The type of accelerator(s) that may be attached to the machine per `accelerator_count`.
    :param accelerator_count: The number of accelerators to attach to the machine.
    :param boot_disk_size_gb: Size in GB of the boot disk

    :return: Callable custom training job.
    """
    job = create_custom_training_job_from_component(
        component_func,
        display_name=display_name,
        replica_count=replica_count,
        machine_type=machine_type,
        accelerator_type=accelerator_type,
        accelerator_count=accelerator_count,
        boot_disk_size_gb=boot_disk_size_gb,
    )

    return lambda: job(config=config)


def submit_pipeline(
    pipeline_func: t.Union[BaseComponent, t.Callable],
    pipeline_display_name: str,
    pipeline_kwargs: t.Dict[str, t.Any],
    project_id: str,
    location: str,
) -> None:
    """
    Create and run a pipeline on Vertex AI Pipelines. Use a temporary file to compile the pipeline config,
    then run the pipeline job and delete the temporary file.

    :param pipeline_func: Pipeline function, must be a function wrapped :func:`kfp.dsl.pipeline` decorator.
    :param pipeline_display_name: A name displayed in the Vertex AI Pipelines UI.
    :param pipeline_kwargs: Keyword arguments to pass to the pipeline function.
    :param project_id: Google Cloud Project ID
    :param location: Datacenter location of Google Cloud Platform to run the pipeline job.
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=".yaml")
    os.environ["GRPC_DNS_RESOLVER"] = "native"

    aiplatform.init(project=project_id, location=location)

    compiler.Compiler().compile(pipeline_func=pipeline_func, package_path=temp_file.name)

    job = aiplatform.PipelineJob(
        display_name=pipeline_display_name,
        template_path=temp_file.name,
        parameter_values=pipeline_kwargs,
    )

    job.submit()
    temp_file.close()
