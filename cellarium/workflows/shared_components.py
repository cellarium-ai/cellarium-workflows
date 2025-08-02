"""Shared component code for cellarium workflows."""
import os
from pathlib import Path

def _load_script_as_string(script_name: str) -> str:
    """Load a Python script from the scripts directory as a string."""
    scripts_dir = Path(__file__).parent / "scripts"
    script_path = scripts_dir / f"{script_name}.py"
    
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")
    
    with open(script_path, "r") as f:
        content = f.read()
    
    # Remove the docstring and any module-level comments for cleaner execution
    lines = content.split('\n')
    # Skip lines that are just comments or docstrings at the top
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and not stripped.startswith('"""') and not stripped.startswith("'''"):
            start_idx = i
            break
    
    return '\n'.join(lines[start_idx:])

def get_pytorch_setup_code() -> str:
    """Returns the PyTorch setup code as a string."""
    return _load_script_as_string("pytorch_setup")

def get_git_install_code() -> str:
    """Returns the git installation code as a string."""
    return _load_script_as_string("git_install")

def get_data_download_code() -> str:
    """Returns the data download code as a string."""
    return _load_script_as_string("data_download")

def get_cellarium_cli_code() -> str:
    """Returns the cellarium CLI execution code as a string."""
    return _load_script_as_string("cellarium_cli")

def _get_train_op_text(copy_data_to_local_disk: bool = True) -> str:
    """
    Returns the ground-truth train_op implementation as a string.
    
    This is the single source of truth for the train_op logic.
    
    Args:
        copy_data_to_local_disk: Whether to include data download code
        
    Returns:
        Complete train_op implementation as a string
    """
    data_download_section = '''
    # optionally copy data from GCS to local disk
    if copy_data_to_local_disk:
        exec(get_data_download_code())
''' if copy_data_to_local_disk else ''
    
    return f'''
# re-install cellarium-ml if a git sha is provided
exec(get_git_install_code())
{data_download_section}
# set up PyTorch environment
exec(get_pytorch_setup_code())

# run the cellarium CLI
exec(get_cellarium_cli_code())
'''.strip()

def create_train_op_function(copy_data_to_local_disk: bool = True):
    """
    Returns a train_op function that can be used for both local and Vertex AI execution.
    
    Args:
        copy_data_to_local_disk: Whether to copy GCS data to local disk
        
    Returns:
        A function that executes the training pipeline
    """
    train_op_text = _get_train_op_text(copy_data_to_local_disk)
    
    def train_op(
        tool: str,
        subcommand: str,
        config: str,
        git_sha: str = "",
    ) -> None:
        # Execute the ground-truth train_op implementation
        exec(train_op_text)
    
    return train_op

def get_train_op_code(copy_data_to_local_disk: bool = True) -> str:
    """
    Returns the complete train_op code as a string for use in dsl.component.
    
    Args:
        copy_data_to_local_disk: Whether to include data download code
        
    Returns:
        Complete train_op implementation as a string
    """
    return _get_train_op_text(copy_data_to_local_disk)

# Re-export utility functions for backward compatibility
def get_current_google_user() -> str | None:
    """Get the current Google user from credentials."""
    try:
        from google.auth import default
        from google.auth.transport.requests import Request
        import jwt
        
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
    """Fetch a URL with retries."""
    import requests
    import time
    
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
    import ast
    import requests
    
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
