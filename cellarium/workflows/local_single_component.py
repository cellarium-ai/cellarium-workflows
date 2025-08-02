"""Run a single component cellarium-ml job locally. Useful for testing."""

import click
from shared_components import create_train_op_function


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
    help="Local or GCS path to the training config YAML file.",
)
@click.option(
    "--copy-data-to-local-disk",
    default=True,
    type=bool,
    help="True copies GCS data to local disk fully (once) before training. False is ephemeral.",
)
@click.option(
    "--git-sha",
    default="",
    type=str,
    help="Cellarium-ML git SHA to install (if provided).",
)
def run_local_single_component(
    tool: str,
    subcommand: str,
    config: str,
    copy_data_to_local_disk: bool,
    git_sha: str,
):
    """
    Run a single component cellarium-ml job locally without Vertex AI.
    
    This is useful for testing and development before submitting to Vertex AI.
    """
    print(f"Running {tool} {subcommand} locally...")
    print(f"Config: {config}")
    print(f"Git SHA: {git_sha}")
    print(f"Copy data to local disk: {copy_data_to_local_disk}")
    
    # Create and run the train operation locally
    train_op = create_train_op_function(copy_data_to_local_disk=copy_data_to_local_disk)
    
    try:
        train_op(
            tool=tool,
            subcommand=subcommand,
            config=config,
            git_sha=git_sha,
        )
        print("Local execution completed successfully!")
    except Exception as e:
        print(f"Local execution failed: {e}")
        raise


if __name__ == "__main__":
    run_local_single_component()
