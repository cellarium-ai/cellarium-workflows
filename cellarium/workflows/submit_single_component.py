import ast
import requests
import tempfile
import time

import click
from google.cloud import aiplatform
from google_cloud_pipeline_components.v1.custom_job import (
    create_custom_training_job_from_component,
)
from google.auth import default
from google.auth.transport.requests import Request
import jwt
from kfp import compiler, dsl


def get_current_google_user() -> str | None:
    try:
        credentials, _ = default()
        credentials.refresh(Request())
        id_token = credentials.id_token
        decoded_token = jwt.decode(id_token, options={"verify_signature": False})
        return decoded_token.get("email").split("@")[0]
    except Exception as e:
        print(
            "NOTE: unable to prepend google user name to pipeline name. "
            f"This is purely cosmetic. Continuing. Error was:\n{e}"
        )
        return None


def fetch_url_with_retries(url, retries=3, delay=1):
    for attempt in range(retries):
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise e


def get_allowed_cli_tool_names(url: str) -> list[str] | None:
    """
    Parse python code at a given URL to obtain a list of allowed cellarium-ml CLI tool names.

    Args:
        url: URL to fetch the python code from.

    Returns:
        List of allowed CLI tool names, or None if the URL could not be fetched.
    """
    try:
        response = fetch_url_with_retries(url)
        content = response.text
        module = ast.parse(content)
        cli_tool_names = [
            node.name
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and any(
                isinstance(decorator, ast.Name) and decorator.id == "register_model"
                for decorator in node.decorator_list
            )
        ]
        return cli_tool_names
    except requests.exceptions.RequestException as e:
        print(
            f"WARNING:\nAttempted to fetch URL {url} to look up allowed CLI tool names.\n"
            "This URL was inferred from the --base-image tag and assumes the tag matches a git SHA for cellarium-ml.\n"
            f"Request returned:\n{e}\n"
            "NOTE: The input --tool cannot be validated. Double check tool name!\n"
        )
        return None


@click.command()
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
    default="n1-standard-4",
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

    @dsl.component(
        packages_to_install=[
            "gcsfs",  # necessary to allow config file outputs to /gcs/bucket/path to be copied to GCS
            "tensorboard",  # necessary to write tensorboard logs
            "psutil",  # necessary to log CPU stats
        ],
        base_image=base_image,
    )
    def train_op(tool: str, subcommand: str, config: str, git_sha: str = "") -> None:
        import os

        # re-install cellarium-ml if a git sha is provided
        if git_sha != "":
            cmd = f"pip install -U git+https://github.com/cellarium-ai/cellarium-ml.git@{git_sha}"
            os.system(cmd)

        # handle multi-node training
        if os.environ.get("RANK") is not None:
            os.environ["NODE_RANK"] = os.environ.get("RANK")

        from cellarium.ml.cli import main as cellarium_ml_cli

        cellarium_ml_cli(args=[tool, subcommand, "--config", config])

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
            git_sha=git_sha,
        ).set_display_name(display_name)

    with tempfile.NamedTemporaryFile(suffix=".yaml") as f:
        compiler.Compiler().compile(pipeline_func=pipeline, package_path=f.name)

        job = aiplatform.PipelineJob(
            display_name=display_name,
            template_path=f.name,
        )

        job.submit()


if __name__ == "__main__":
    submit_single_component_pipeline()
