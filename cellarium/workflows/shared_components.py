"""Shared component code for cellarium workflows."""
import os
import yaml
import gcsfs
from pathlib import Path


mount_path = "/mnt/share/gcs_output"


def extract_output_gcs_bucket_from_config(config_path: str) -> str:
    """
    Extract the output GCS bucket path from the config file's trainer.default_root_dir.
    
    Args:
        config_path: Path to the config YAML file (local or gs://)
        
    Returns:
        GCS bucket path (e.g., 'gs://bucket/path') or empty string if not found/not GCS
    """
    try:
        # Load the config file content as text
        if config_path.startswith('gs://'):
            fs = gcsfs.GCSFileSystem()
            with fs.open(config_path, 'r') as f:
                content = f.read()
        else:
            with open(config_path, 'r') as f:
                content = f.read()
        
        # Use regex to find default_root_dir value
        import re
        
        # Look for default_root_dir: followed by the path
        pattern = r'default_root_dir:\s*([^\s\n]+)'
        match = re.search(pattern, content)
        
        if not match:
            print("📁 No default_root_dir found in config")
            return ""
        
        default_root_dir = match.group(1).strip()
        
        # Check if it's a GCS path
        if default_root_dir.startswith('gs://'):
            print(f"📋 Detected GCS output path: {default_root_dir}")
            return default_root_dir
        elif default_root_dir.startswith('/gcs/'):
            # Convert /gcs/bucket/path format to gs://bucket/path
            gcs_path = default_root_dir[5:]  # Remove '/gcs/' prefix
            if '/' in gcs_path:
                bucket, path = gcs_path.split('/', 1)
                gcs_url = f"gs://{bucket}/{path}"
            else:
                gcs_url = f"gs://{gcs_path}"
            print(f"📋 Detected GCS output path: {default_root_dir} -> {gcs_url}")
            return gcs_url
        else:
            print(f"📁 Local output path detected: {default_root_dir}")
            return ""
            
    except Exception as e:
        print(f"⚠️  Warning: Could not parse config for output path: {e}")
        return ""


def get_machine_type_resources(machine_type: str) -> tuple[int, int]:
    """
    Get CPU (in milliCPU) and memory (in MiB) for a given machine type.
    
    Args:
        machine_type: Machine type string (e.g., 'n1-standard-4')
        
    Returns:
        Tuple of (cpu_milli, memory_mib)
    """
    # Common machine type mappings
    # Format: machine_type -> (cpu_milli, memory_mib)
    machine_type_specs = {
        # N1 Standard series
        "n1-standard-1": (1000, 3840),      # 1 vCPU, 3.75 GB
        "n1-standard-2": (2000, 7680),      # 2 vCPU, 7.5 GB
        "n1-standard-4": (4000, 15360),     # 4 vCPU, 15 GB
        "n1-standard-8": (8000, 30720),     # 8 vCPU, 30 GB
        "n1-standard-16": (16000, 61440),   # 16 vCPU, 60 GB
        "n1-standard-32": (32000, 122880),  # 32 vCPU, 120 GB
        "n1-standard-64": (64000, 245760),  # 64 vCPU, 240 GB
        "n1-standard-96": (96000, 368640),  # 96 vCPU, 360 GB
        
        # N1 High-memory series
        "n1-highmem-1": (1000, 6656),       # 1 vCPU, 6.5 GB
        "n1-highmem-2": (2000, 13312),      # 2 vCPU, 13 GB
        "n1-highmem-4": (4000, 26624),      # 4 vCPU, 26 GB
        "n1-highmem-8": (8000, 53248),      # 8 vCPU, 52 GB
        "n1-highmem-16": (16000, 106496),   # 16 vCPU, 104 GB
        "n1-highmem-32": (32000, 212992),   # 32 vCPU, 208 GB
        "n1-highmem-64": (64000, 425984),   # 64 vCPU, 416 GB
        "n1-highmem-96": (96000, 638976),   # 96 vCPU, 624 GB
        
        # N1 High-CPU series
        "n1-highcpu-2": (2000, 1843),       # 2 vCPU, 1.8 GB
        "n1-highcpu-4": (4000, 3686),       # 4 vCPU, 3.6 GB
        "n1-highcpu-8": (8000, 7373),       # 8 vCPU, 7.2 GB
        "n1-highcpu-16": (16000, 14746),    # 16 vCPU, 14.4 GB
        "n1-highcpu-32": (32000, 29491),    # 32 vCPU, 28.8 GB
        "n1-highcpu-64": (64000, 58982),    # 64 vCPU, 57.6 GB
        "n1-highcpu-96": (96000, 88474),    # 96 vCPU, 86.4 GB
        
        # N2 Standard series
        "n2-standard-2": (2000, 8192),      # 2 vCPU, 8 GB
        "n2-standard-4": (4000, 16384),     # 4 vCPU, 16 GB
        "n2-standard-8": (8000, 32768),     # 8 vCPU, 32 GB
        "n2-standard-16": (16000, 65536),   # 16 vCPU, 64 GB
        "n2-standard-32": (32000, 131072),  # 32 vCPU, 128 GB
        "n2-standard-48": (48000, 196608),  # 48 vCPU, 192 GB
        "n2-standard-64": (64000, 262144),  # 64 vCPU, 256 GB
        "n2-standard-80": (80000, 327680),  # 80 vCPU, 320 GB
        "n2-standard-96": (96000, 393216),  # 96 vCPU, 384 GB
        "n2-standard-128": (128000, 524288), # 128 vCPU, 512 GB
        
        # N2 High-memory series
        "n2-highmem-2": (2000, 16384),      # 2 vCPU, 16 GB
        "n2-highmem-4": (4000, 32768),      # 4 vCPU, 32 GB
        "n2-highmem-8": (8000, 65536),      # 8 vCPU, 64 GB
        "n2-highmem-16": (16000, 131072),   # 16 vCPU, 128 GB
        "n2-highmem-32": (32000, 262144),   # 32 vCPU, 256 GB
        "n2-highmem-48": (48000, 393216),   # 48 vCPU, 384 GB
        "n2-highmem-64": (64000, 524288),   # 64 vCPU, 512 GB
        "n2-highmem-80": (80000, 655360),   # 80 vCPU, 640 GB
        "n2-highmem-96": (96000, 786432),   # 96 vCPU, 768 GB
        "n2-highmem-128": (128000, 884736), # 128 vCPU, 864 GB
        
        # N2 High-CPU series
        "n2-highcpu-2": (2000, 2048),       # 2 vCPU, 2 GB
        "n2-highcpu-4": (4000, 4096),       # 4 vCPU, 4 GB
        "n2-highcpu-8": (8000, 8192),       # 8 vCPU, 8 GB
        "n2-highcpu-16": (16000, 16384),    # 16 vCPU, 16 GB
        "n2-highcpu-32": (32000, 32768),    # 32 vCPU, 32 GB
        "n2-highcpu-48": (48000, 49152),    # 48 vCPU, 48 GB
        "n2-highcpu-64": (64000, 65536),    # 64 vCPU, 64 GB
        "n2-highcpu-80": (80000, 81920),    # 80 vCPU, 80 GB
        "n2-highcpu-96": (96000, 98304),    # 96 vCPU, 96 GB
        
        # C2 High-CPU series
        "c2-standard-4": (4000, 16384),     # 4 vCPU, 16 GB
        "c2-standard-8": (8000, 32768),     # 8 vCPU, 32 GB
        "c2-standard-16": (16000, 65536),   # 16 vCPU, 64 GB
        "c2-standard-30": (30000, 122880),  # 30 vCPU, 120 GB
        "c2-standard-60": (60000, 245760),  # 60 vCPU, 240 GB
        
        # E2 series
        "e2-standard-2": (2000, 8192),      # 2 vCPU, 8 GB
        "e2-standard-4": (4000, 16384),     # 4 vCPU, 16 GB
        "e2-standard-8": (8000, 32768),     # 8 vCPU, 32 GB
        "e2-standard-16": (16000, 65536),   # 16 vCPU, 64 GB
        "e2-standard-32": (32000, 131072),  # 32 vCPU, 128 GB
        
        # A2 GPU-optimized series
        "a2-highgpu-1g": (12000, 87040),    # 12 vCPU, 85 GB, 1 A100
        "a2-highgpu-2g": (24000, 174080),   # 24 vCPU, 170 GB, 2 A100
        "a2-highgpu-4g": (48000, 348160),   # 48 vCPU, 340 GB, 4 A100
        "a2-highgpu-8g": (96000, 696320),   # 96 vCPU, 680 GB, 8 A100
        "a2-megagpu-16g": (96000, 1392640), # 96 vCPU, 1360 GB, 16 A100
        
        # G2 GPU-optimized series
        "g2-standard-4": (4000, 16384),     # 4 vCPU, 16 GB, 1 L4
        "g2-standard-8": (8000, 32768),     # 8 vCPU, 32 GB, 1 L4
        "g2-standard-12": (12000, 49152),   # 12 vCPU, 48 GB, 1 L4
        "g2-standard-16": (16000, 65536),   # 16 vCPU, 64 GB, 1 L4
        "g2-standard-24": (24000, 98304),   # 24 vCPU, 96 GB, 2 L4
        "g2-standard-32": (32000, 131072),  # 32 vCPU, 128 GB, 1 L4
        "g2-standard-48": (48000, 196608),  # 48 vCPU, 192 GB, 4 L4
        "g2-standard-96": (96000, 393216),  # 96 vCPU, 384 GB, 8 L4
    }
    
    if machine_type in machine_type_specs:
        cpu_milli, memory_mib = machine_type_specs[machine_type]
        print(f"📋 Machine type {machine_type}: {cpu_milli//1000} vCPU, {memory_mib//1024:.1f} GB")
        return cpu_milli, memory_mib
    else:
        # For unknown machine types, use conservative defaults
        print(f"⚠️  Unknown machine type '{machine_type}', using defaults: 2 vCPU, 2 GB")
        print(f"   Consider adding this machine type to the mapping for optimal resource allocation")
        return 2000, 2048  # 2 vCPU, 2 GB


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

# Create Python wrapper script that properly handles environment variables and config path replacement
cat > /tmp/train_op_wrapper.py << 'WRAPPER_EOF'
import os
import tempfile
import yaml
import shutil
from pathlib import Path

# Get environment variables
tool = os.environ.get('TOOL')
subcommand = os.environ.get('SUBCOMMAND')
config = os.environ.get('CONFIG')
git_sha = os.environ.get('GIT_SHA')
copy_data_to_local_disk = os.environ.get('COPY_DATA_TO_LOCAL_DISK', 'false').lower() == 'true'

# Check if GCS volume is mounted and create modified config if needed
original_config = config
if os.path.exists('{mount_path}'):
    print(f"✅ GCS volume mounted at {mount_path} - applying config path substitution")

    # Load the original config
    # The config should already be accessible locally at this point
    try:
        with open(config, 'r') as f:
            config_content = f.read()
    except FileNotFoundError:
        print(f"⚠️  Config file not found at {config}, attempting to download from GCS")
        if config.startswith('gs://'):
            # Fallback: download from GCS if not found locally
            import subprocess
            temp_original = '/tmp/original_config.yaml'
            subprocess.run(['gsutil', 'cp', config, temp_original], check=True)
            with open(temp_original, 'r') as f:
                config_content = f.read()
        else:
            raise
    
    # Replace /gcs/ paths with /mnt/share/gcs_output/ in the config content
    modified_content = config_content.replace('/gcs/', f'{mount_path}/')

    # Write modified config to a temporary file
    temp_config = '/tmp/modified_config.yaml'
    with open(temp_config, 'w') as f:
        f.write(modified_content)
    
    # Update config path to use the modified version
    config = temp_config
    print(f"📝 Created modified config with updated paths: {{config}}")
    
    # Log the changes made
    if '/gcs/' in config_content:
        print(f"🔄 Replaced /gcs/ paths with {mount_path} in config")
    else:
        print("ℹ️  No /gcs/ paths found in config - no substitution needed")
else:
    print("📁 GCS volume not mounted - using original config paths")

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
