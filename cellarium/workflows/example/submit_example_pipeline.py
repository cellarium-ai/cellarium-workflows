import click

from cellarium.workflows.example import pipelines
from cellarium.workflows import kfp_helpers


@click.command()
@click.option("--project_id")
@click.option("--location")
@click.option("--display_name")
@click.option("--component_1_config")
@click.option("--component_2_config")
def submit_example(project_id: str, location: str, display_name: str, component_1_config: str, component_2_config: str):
    kfp_helpers.submit_pipeline(
        pipeline_func=pipelines.example_pipeline,
        project_id=project_id,
        location=location,
        pipeline_display_name=display_name,
        pipeline_kwargs={"component_1_config": component_1_config, "component_2_config": component_2_config}
    )
    print("Submitted pipeline!")


if __name__ == "__main__":
    submit_example()
