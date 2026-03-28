import tempfile

import click
from google.cloud import aiplatform
from google_cloud_pipeline_components.v1.custom_job import (
    create_custom_training_job_from_component,
)
from kfp import compiler, dsl

from .shared_components import (
    get_current_google_user,
    get_allowed_cli_tool_names,
    get_train_op_code,
    create_vertex_ai_train_op_component,
)


@click.command(short_help="Submit a single-component job to Vertex AI Pipelines.")
@click.option(
    "--tool",
    required=True,
    help="Tool to run, e.g. 'onepass_mean_var_std'.",
)
@click.option(
    "--subcommand",
    required=True,
    type=click.Choice(["fit", "predict"]),
    help="Subcommand to run, either 'fit' or 'predict'.",
)
@click.option(
    "--config",
    required=True,
    help="GCS path to the training config YAML file.",
)
@click.option(
    "--copy-data-to-local-disk",
    default=True,
    type=bool,
    help="True copies GCS data to local disk fully (once) before training. False is ephemeral.",
)
@click.option(
    "--project",
    default="dsp-cell-annotation-service",
    help="Google Cloud project ID.",
)
@click.option(
    "--location",
    default="us-central1",
    help="Google Cloud location, e.g. 'us-central1'.",
)
@click.option(
    "--pipeline-name",
    default="",
    help="Pipeline name, defaults to f'{user}_{tool}_{subcommand}'.",
)
@click.option(
    "--machine-type",
    default="n1-standard-8",
    help="Machine type for the training job, e.g. 'n1-standard-16'.",
)
@click.option(
    "--replica-count",
    default=1,
    type=int,
    help="Number of replicas (nodes) for training.",
)
@click.option(
    "--accelerator-type",
    default="NVIDIA_TESLA_T4",
    help="Type of accelerator (gpu), e.g. 'NVIDIA_TESLA_T4'.",
)
@click.option(
    "--accelerator-count",
    default=1,
    type=int,
    help="Number of GPUs.",
)
@click.option(
    "--git-sha",
    default="",
    type=str,
    help="Cellarium-ML git SHA to install (if provided).",
)
@click.option(
    "--base-image",
    default="us-central1-docker.pkg.dev/broad-dsde-methods/cellarium-ai/cellarium-ml:cellarium-gpt-cstorch",
    help="Base image for the component.",
)
def submit_single_component_pipeline(
    project: str,
    location: str,
    config: str,
    tool: str,
    subcommand: str,
    copy_data_to_local_disk: bool,
    pipeline_name: str,
    machine_type: str,
    replica_count: int,
    accelerator_type: str,
    accelerator_count: int,
    git_sha: str,
    base_image: str,
):
    """
    Submit a single component cellarium-ml pipeline to Vertex AI Pipelines.
    """
    # input validation and defaults
    display_name = f"{tool}_{subcommand}"
    if pipeline_name == "":
        user = get_current_google_user()
        if user is not None:
            pipeline_name = f"{user}_{display_name}"
        else:
            pipeline_name = display_name
    if (git_sha == "") and (len(base_image.split(":")[-1]) > 0):
        git_sha = base_image.split(":")[-1]
    url = f"https://raw.githubusercontent.com/cellarium-ai/cellarium-ml/{git_sha}/cellarium/ml/cli.py"
    cli_tool_names = get_allowed_cli_tool_names(url)
    if cli_tool_names is not None:
        if tool not in cli_tool_names:
            raise ValueError(
                f"Tool '{tool}' not found in allowed CLI tools at {url}.\n"
                f"Allowed tool names:\n{cli_tool_names}"
            )
    if (
        (accelerator_count is None)
        or (accelerator_type is None)
        or (accelerator_count == 0)
    ):
        # vertex ai wants None for both inputs if one of them is None
        accelerator_count = None
        accelerator_type = None

    aiplatform.init(project=project, location=location)

    # Create the train_op component using our dynamic creator
    train_op = create_vertex_ai_train_op_component(base_image)
    
    # Get the train_op code that will be passed as a parameter
    train_op_code = get_train_op_code(copy_data_to_local_disk)

    custom_training_job = create_custom_training_job_from_component(
        train_op,
        display_name=display_name,
        replica_count=replica_count,
        machine_type=machine_type,
        accelerator_type=accelerator_type,
        accelerator_count=accelerator_count,
    )

    @dsl.pipeline(name=pipeline_name, description=f"cellarium-ml {tool} {subcommand}")
    def pipeline():
        custom_training_job(
            project=project,
            location=location,
            tool=tool,
            subcommand=subcommand,
            config=config,
            train_op_code=train_op_code,
            git_sha=git_sha,
            copy_data_to_local_disk=copy_data_to_local_disk,
        ).set_display_name(display_name)

    with tempfile.NamedTemporaryFile(suffix=".yaml") as f:
        compiler.Compiler().compile(pipeline_func=pipeline, package_path=f.name)

        job = aiplatform.PipelineJob(
            display_name=display_name,
            template_path=f.name,
            enable_caching=False,  # by default this is True
        )

        job.submit()


if __name__ == "__main__":
    submit_single_component_pipeline()
