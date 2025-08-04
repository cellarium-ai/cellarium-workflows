"""Shared component code for cellarium workflows."""
import os
from pathlib import Path

def get_train_op_requirements() -> list[str]:
    """Load the train_op requirements from the requirements file."""
    requirements_file = Path(__file__).parent.parent.parent / "requirements" / "train_op.txt"
    
    if not requirements_file.exists():
        # Fallback to hardcoded list if file doesn't exist
        return [
            "gcsfs",
            "tensorboard", 
            "psutil",
            "ruamel.yaml",
        ]
    
    requirements = []
    with open(requirements_file, "r") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                # Extract package name (remove inline comments)
                package = line.split('#')[0].strip()
                if package:
                    requirements.append(package)
    
    return requirements

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

def _load_bash_script_as_string(script_name: str) -> str:
    """Load a bash script from the scripts directory as a string."""
    scripts_dir = Path(__file__).parent / "scripts"
    script_path = scripts_dir / f"{script_name}.sh"
    
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")
    
    with open(script_path, "r") as f:
        content = f.read()
    
    return content

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
        Complete train_op implementation as a string with inlined script content
    """
    # Get the actual script content and inline it
    git_install_code = get_git_install_code()
    pytorch_setup_code = get_pytorch_setup_code()
    cellarium_cli_code = get_cellarium_cli_code()
    
    if copy_data_to_local_disk:
        data_download_code = get_data_download_code()
        data_download_section = f'''
# optionally copy data from GCS to local disk
if copy_data_to_local_disk:
{_indent_code(data_download_code, 4)}
'''
    else:
        data_download_section = ''
    
    return f'''# re-install cellarium-ml if a git sha is provided
{git_install_code}
{data_download_section}# set up PyTorch environment
{pytorch_setup_code}

# run the cellarium CLI
{cellarium_cli_code}'''.strip()

def _indent_code(code: str, spaces: int) -> str:
    """Indent each line of code by the specified number of spaces."""
    indent = " " * spaces
    return "\n".join(indent + line if line.strip() else line for line in code.split("\n"))

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
        # Create execution context with all necessary variables and functions
        exec_globals = {
            'tool': tool,
            'subcommand': subcommand,
            'config': config,
            'git_sha': git_sha,
            'copy_data_to_local_disk': copy_data_to_local_disk,
            'get_git_install_code': get_git_install_code,
            'get_data_download_code': get_data_download_code,
            'get_pytorch_setup_code': get_pytorch_setup_code,
            'get_cellarium_cli_code': get_cellarium_cli_code,
        }
        # Execute the ground-truth train_op implementation
        exec(train_op_text, exec_globals)
    
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

def get_batch_setup_script() -> str:
    """Returns the batch setup script as a string."""
    return _load_bash_script_as_string("batch_setup")

def create_batch_script(
    tool: str,
    subcommand: str,
    config: str,
    git_sha: str,
    copy_data_to_local_disk: bool,
    capture_logs_to_gcs: bool = False,
) -> str:
    """
    Create a batch script for Google Cloud Batch execution.
    
    This generates the complete bash script that sets up the environment
    and executes the train_op code.
    
    Args:
        tool: Cellarium tool to run
        subcommand: Subcommand (fit/predict)
        config: Path to config file
        git_sha: Git SHA for cellarium-ml
        copy_data_to_local_disk: Whether to copy data locally
        capture_logs_to_gcs: Whether to capture logs to GCS
        
    Returns:
        Complete bash script as a string
    """
    train_op_code = get_train_op_code(copy_data_to_local_disk)
    train_op_requirements = get_train_op_requirements()
    batch_setup_script = get_batch_setup_script()
    
    return f'''#!/bin/bash
set -e

# Set up environment variables for the setup script
export TOOL="{tool}"
export SUBCOMMAND="{subcommand}"
export CONFIG="{config}"
export GIT_SHA="{git_sha}"
export COPY_DATA_TO_LOCAL_DISK="{copy_data_to_local_disk}"
export CELLARIUM_CAPTURE_LOGS="{str(capture_logs_to_gcs).lower()}"
export TRAIN_OP_REQUIREMENTS="{' '.join(train_op_requirements)}"

# Run the batch setup script
cat > /tmp/batch_setup.sh << 'SETUP_EOF'
{batch_setup_script}
SETUP_EOF

chmod +x /tmp/batch_setup.sh
/tmp/batch_setup.sh

# Create Python wrapper script that properly handles environment variables
cat > /tmp/train_op_wrapper.py << 'WRAPPER_EOF'
import os

# Get environment variables
tool = os.environ.get('TOOL')
subcommand = os.environ.get('SUBCOMMAND')
config = os.environ.get('CONFIG')
git_sha = os.environ.get('GIT_SHA')
copy_data_to_local_disk = os.environ.get('COPY_DATA_TO_LOCAL_DISK', 'false').lower() == 'true'

# Execute train_op code with proper variable scope
{train_op_code}
WRAPPER_EOF

# Execute the training operation
echo "🚀 Starting training operation..."
python3 /tmp/train_op_wrapper.py
'''

def create_vertex_ai_train_op_component(base_image: str = ""):
    """
    Creates a dsl.component decorated train_op function for Vertex AI execution.
    
    This passes the train_op_code as a parameter so it gets serialized properly.
    
    Args:
        base_image: The base image for the component
        
    Returns:
        A dsl.component decorated function ready for Vertex AI
    """
    from kfp import dsl
    
    @dsl.component(
        packages_to_install=get_train_op_requirements(),
        base_image=base_image,
    )
    def train_op(
        tool: str,
        subcommand: str,
        config: str,
        train_op_code: str,  # Pass the code as a parameter
        git_sha: str = "",
        copy_data_to_local_disk: bool = True,
    ) -> None:
        # Create execution context with all necessary variables
        exec_globals = {
            'tool': tool,
            'subcommand': subcommand,
            'config': config,
            'git_sha': git_sha,
            'copy_data_to_local_disk': copy_data_to_local_disk,
        }
        # Execute the train_op code with proper context
        exec(train_op_code, exec_globals)
    
    return train_op

# Re-export utility functions for backward compatibility
def get_current_google_user():
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

def get_allowed_cli_tool_names(url: str):
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
