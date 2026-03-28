import tempfile
import yaml

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


def parse_pipeline_yaml(config: str) -> tuple[str, list[dict]]:
    with open(config) as f:
        config_contents = yaml.safe_load(f)
    top_level_keys = list(config_contents.keys())
    assert (
        len(top_level_keys) == 1
    ), "Pipeline YAML config error: The top level of the config file must be the display_name of the pipeline. Only one top level key is allowed."
    display_name = list(config_contents.keys())[0]
    component_definitions = config_contents[display_name]
    assert isinstance(
        component_definitions, list
    ), "Pipeline YAML config error: The value of the top level key must be a list of component definition dictionaries."
    for item in component_definitions:
        assert isinstance(
            item, dict
        ), "Pipeline YAML config error: Each component definition in the list must be a dictionary."
        assert (
            "tool" in item
        ), "Pipeline YAML config error: Each component definition must have a 'tool' key."
        assert (
            "subcommand" in item
        ), "Pipeline YAML config error: Each component definition must have a 'subcommand' key."
        assert (
            item["subcommand"] in ["fit", "predict"]
        ), "Pipeline YAML config error: The 'subcommand' key's value must be either 'fit' or 'predict'."
        assert (
            "config" in item
        ), "Pipeline YAML config error: Each component definition must have a 'config' key."
    return display_name, component_definitions


@click.command(short_help="Submit a multi-step sequential pipeline to Vertex AI Pipelines.")
@click.option(
    "--pipeline-config",
    required=True,
    help="Local path to the pipeline config YAML file.",
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
    "--copy-data-to-local-disk",
    default=True,
    type=bool,
    help="True copies GCS data to local disk fully (once) before training. False is ephemeral.",
)
@click.option(
    "--base-image",
    default="us-central1-docker.pkg.dev/broad-dsde-methods/cellarium-ai/cellarium-ml:cellarium-gpt-cstorch",
    help="Base image for the component.",
)
def submit_sequential_pipeline(
    project: str,
    location: str,
    pipeline_config: str,
    pipeline_name: str,
    copy_data_to_local_disk: bool,
    base_image: str,
):
    """
    Submit a pipeline of sequential cellarium-ml tools to Vertex AI Pipelines.

    Example contents of pipeline-config:

    .. code-block:: yaml

        scvi_vanilla_with_full_latent_batch:

            - tool: scvi

                subcommand: fit

                config: gs://cellarium-human-primary-data/curriculum/human_all_primary_20241108/configs/20241120_scvi_train_config.yaml

                machine_type: n1-standard-16

                accelerator_type: NVIDIA_TESLA_T4

                accelerator_count: 4

                git_sha: c14705370d2a7a805286fa3dd0e4795c10e6cefd

    """
    # parse pipeline config
    display_name, component_definitions = parse_pipeline_yaml(pipeline_config)

    # input validation and defaults
    if pipeline_name == "":
        user = get_current_google_user()
        if user is not None:
            pipeline_name = f"{user}_{display_name}"
        else:
            pipeline_name = display_name

    for t, sha in [(c["tool"], c.get("git_sha", "")) for c in component_definitions]:
        if (sha == "") and (len(base_image.split(":")[-1]) > 0):
            sha = base_image.split(":")[-1]
        url = f"https://raw.githubusercontent.com/cellarium-ai/cellarium-ml/{sha}/cellarium/ml/cli.py"
        cli_tool_names = get_allowed_cli_tool_names(url)
        if cli_tool_names is not None:
            if t not in cli_tool_names:
                raise ValueError(
                    f"Tool '{t}' not found in allowed CLI tools at {url}.\n"
                    f"Allowed tool names:\n{cli_tool_names}"
                )
    for subcommand in [c["subcommand"] for c in component_definitions]:
        if subcommand not in ["fit", "predict"]:
            raise ValueError(
                f"Subcommand '{subcommand}' not recognized. Must be either 'fit' or 'predict'."
            )
    for i, c in enumerate(component_definitions):
        accelerator_type = c.get("accelerator_type", None)
        accelerator_count = c.get("accelerator_count", None)
        if (
            (accelerator_count is None)
            or (accelerator_type is None)
            or (accelerator_count == 0)
        ):
            # vertex ai wants None for both inputs if one of them is None
            component_definitions[i]["accelerator_count"] = None
            component_definitions[i]["accelerator_type"] = None

    aiplatform.init(project=project, location=location)

    # Create the train_op component using our dynamic creator
    train_op = create_vertex_ai_train_op_component(base_image)
    
    # Get the train_op code that will be passed as a parameter
    train_op_code = get_train_op_code(copy_data_to_local_disk)

    # create component definitions
    custom_training_jobs = [
        create_custom_training_job_from_component(
            train_op,
            display_name=f"{i}__{c['tool']}_{c['subcommand']}",
            replica_count=c.get("replica_count", 1),
            machine_type=c.get("machine_type", None),
            accelerator_type=c.get("accelerator_type", None),
            accelerator_count=c.get("accelerator_count", None),
        )
        for i, c in enumerate(component_definitions)
    ]

    @dsl.pipeline(name=pipeline_name, description="cellarium-ml sequence")
    def pipeline():
        tasks = []
        for i, (component_definition, custom_training_job) in enumerate(
            zip(component_definitions, custom_training_jobs)
        ):
            task = custom_training_job(
                project=project,
                location=location,
                tool=component_definition["tool"],
                subcommand=component_definition["subcommand"],
                config=component_definition["config"],
                train_op_code=train_op_code,
                git_sha=component_definition.get("git_sha", ""),
                copy_data_to_local_disk=copy_data_to_local_disk,
            ).set_display_name(
                f"{i}__{component_definition['tool']}_{component_definition['subcommand']}"
            )
            if tasks:  # Set dependency if there's a previous task
                task.after(tasks[-1])
            tasks.append(task)

    with tempfile.NamedTemporaryFile(suffix=".yaml") as f:
        compiler.Compiler().compile(pipeline_func=pipeline, package_path=f.name)

        job = aiplatform.PipelineJob(
            display_name=display_name,
            template_path=f.name,
        )

        job.submit()


if __name__ == "__main__":
    submit_sequential_pipeline()
