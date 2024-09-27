from kfp import dsl


@dsl.component(base_image="python:3.10-slim")
def example_component_1(config: str):
    """
    Test Example component
    """
    print(config)
    print("Example component is being executed....")


@dsl.component(base_image="python:3.10-slim")
def example_component_2(config: str):
    """
    Test Example component
    """
    print(config)
    print("Second example component is being executed...")
