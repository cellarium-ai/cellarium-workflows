from kfp import dsl
from cellarium.workflows import kfp_helpers
from cellarium.workflows.example import components


@dsl.pipeline()
def example_pipeline(component_1_config: str, component_2_config: str):
    """
    KFP pipeline to run PCA train pipeline.

    """
    component_job_1 = kfp_helpers.create_job(
        component_func=components.example_component_1,
        display_name="Example Job 1",
        config=component_1_config
    )

    component_job_2 = kfp_helpers.create_job(
        component_func=components.example_component_2,
        display_name="Example Job 2",
        config=component_2_config
    )

    task_1 = component_job_1()
    task_2 = component_job_2()

    task_2.after(task_1)


if __name__ == '__main__':
    example_pipeline()
