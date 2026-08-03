# Cellarium Workflows - Shared Components

This directory contains code for submitting cellarium-ml tasks to Vertex AI Pipelines.

## Structure

```
cellarium/workflows/
├── scripts/                    # Individual Python scripts with full IDE support
│   ├── __init__.py
│   ├── git_install.py         # Git installation logic
│   ├── pytorch_setup.py       # PyTorch environment setup
│   ├── data_download.py       # GCS data download with brace expansion
│   └── cellarium_cli.py       # Cellarium CLI execution
├── shared_components.py        # Module that converts scripts to strings and provides train_op
├── submit_single_component.py  # Single component pipeline submission (Vertex AI)
├── submit_pipeline.py          # Multi-component pipeline submission (Vertex AI)
├── local_single_component.py   # Single component local execution (no Vertex AI)
└── test_shared_components.py   # Test script for validation
```

## Usage

### Local Execution (for testing)
```bash
# Run locally for testing and development, or interactive runs on a VM
(cellarium)$ python local_single_component.py --tool scvi --subcommand fit --config /path/to/config.yaml
```

### Vertex AI Single Component
```bash
# Submit a single component to Vertex AI
(vertex)$ python submit_single_component.py --tool scvi --subcommand fit --config gs://path/to/config.yaml
```

### Vertex AI Multi-Component Pipeline
```bash
# Submit a multi-component pipeline to Vertex AI
(vertex)$ python submit_pipeline.py --pipeline-config pipeline_config.yaml
```

## How It Works

### Core Architecture

1. **Scripts**: Individual Python files in `scripts/` contain the actual logic with full IDE support
2. **Shared Components**: The `shared_components.py` module provides:
   - `_get_train_op_text()`: Ground truth train_op implementation as text
   - `create_train_op_function()`: Creates a function for local execution using `exec()` on the ground truth
   - `get_train_op_code()`: Returns the ground truth text for Vertex AI components
   - Individual code generators for each script
3. **Execution Modes**:
   - **Local**: Uses `create_train_op_function()` which executes the ground truth text
   - **Vertex AI**: Uses `get_train_op_code()` to get the same ground truth text for containerized execution

### Train Op Function

The core training logic is defined once as a ground-truth text template in `_get_train_op_text()` that:
- Installs the specified git SHA of cellarium-ml
- Optionally downloads data from GCS with parallel processing
- Sets up PyTorch environment for optimal performance
- Executes the cellarium CLI

This ground truth is used by:
- `create_train_op_function()` - Wraps the text in a function for local execution
- `get_train_op_code()` - Returns the text directly for Vertex AI component execution
- Both `submit_single_component.py` and `submit_pipeline.py` - Use the text in containerized components
- `local_single_component.py` - Uses the function wrapper for direct execution

This ensures zero redundancy - there's exactly one definition of the training logic.

### Flexible Execution
- **Local Development**: Test your workflows locally before submitting to Vertex AI
- **Single Components**: Submit individual training jobs
- **Multi-Component Pipelines**: Chain multiple training steps with dependencies

## Testing

Run the comprehensive test suite:
```bash
python test_shared_components.py
```

This tests:
- Code generation functions
- Train op function creation
- Import validation for all workflow files
- Utility functions

## Development

### Adding New Shared Functionality

1. Create a new script in `scripts/` with proper imports and logic
2. Add a corresponding function in `shared_components.py`
3. Import and use in your workflow files
4. Update tests as needed

### Using the Train Op Function

For local execution:
```python
from shared_components import create_train_op_function

train_op = create_train_op_function(copy_data_to_local_disk=True)
train_op(tool="scvi", subcommand="fit", config="config.yaml", git_sha="")
```

For Vertex AI components:
```python
from shared_components import get_train_op_code

@dsl.component(...)
def train_op(...):
    exec(get_train_op_code(copy_data_to_local_disk=True))
```

### Variable Context

The scripts can reference variables that will be available in the execution context:
- `tool`, `subcommand`, `config`, `git_sha` - always available
- `copy_data_to_local_disk` - available in functions that use it

## Example Workflow

1. **Develop locally**: Use `local_single_component.py` to test your configuration
2. **Submit single job**: Use `submit_single_component.py` for one-off training
3. **Scale to pipeline**: Use `submit_pipeline.py` for multi-step workflows
