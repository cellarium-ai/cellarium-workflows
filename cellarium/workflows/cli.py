"""Main CLI entry point for cellarium-workflows."""

import click

from .local_single_component import run_local_single_component
from .submit_batch_component import submit_batch_component
from .submit_batch_pipeline import submit_batch_pipeline
from .submit_vertex_component import submit_single_component_pipeline
from .submit_vertex_pipeline import submit_sequential_pipeline


@click.group()
def cli():
    """Cellarium workflow submission tools."""
    pass


cli.add_command(submit_batch_component, name="submit-batch-component")
cli.add_command(submit_batch_pipeline, name="submit-batch-pipeline")
cli.add_command(submit_single_component_pipeline, name="submit-vertex-component")
cli.add_command(submit_sequential_pipeline, name="submit-vertex-pipeline")
cli.add_command(run_local_single_component, name="local-single-component")


if __name__ == "__main__":
    cli()
