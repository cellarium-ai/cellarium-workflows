#!/bin/bash
# Google Cloud Batch setup script for Cellarium ML training jobs
# This script installs Python packages and sets up the environment
# Note: GPU drivers are automatically installed by Google Cloud Batch when GPUs are allocated

set -e

# Set environment variables to prevent interactive prompts
export DEBIAN_FRONTEND=noninteractive
export TZ=UTC
export NEEDRESTART_MODE=a  # Automatic restart services without prompting

echo "🚀 Starting Google Cloud Batch setup..."

# Comprehensive GPU diagnostics
echo "🔍 GPU Diagnostics..."
echo "Environment variables:"
echo "  CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES:-not set}"
echo "  NVIDIA_VISIBLE_DEVICES: ${NVIDIA_VISIBLE_DEVICES:-not set}"

# echo "Checking for GPU hardware..."
# if lspci | grep -i nvidia; then
#     echo "✅ NVIDIA hardware detected"
# else
#     echo "❌ No NVIDIA hardware found in lspci"
# fi

echo "Checking for nvidia-smi..."
if command -v nvidia-smi &> /dev/null; then
    echo "✅ nvidia-smi command available"
    echo "Running nvidia-smi..."
    nvidia-smi || echo "❌ nvidia-smi failed to run"
else
    echo "❌ nvidia-smi command not found"
    echo "Checking if GPU drivers are installed..."
    ls /usr/bin/nvidia-* 2>/dev/null || echo "No nvidia binaries found in /usr/bin/"
    ls /dev/nvidia* 2>/dev/null || echo "No nvidia device files found in /dev/"
fi

echo "Checking Docker GPU runtime..."
if docker info 2>/dev/null | grep -i nvidia; then
    echo "✅ Docker NVIDIA runtime detected"
else
    echo "⚠️  Docker NVIDIA runtime not detected"
fi

# Install required Python packages
echo "📦 Installing Python packages..."
if [ ! -z "$TRAIN_OP_REQUIREMENTS" ]; then
    echo "Installing: $TRAIN_OP_REQUIREMENTS"
    pip install -q $TRAIN_OP_REQUIREMENTS
    echo "✅ Python packages installed successfully"
else
    echo "⚠️  No TRAIN_OP_REQUIREMENTS specified"
fi

# PyTorch GPU test
echo "🧪 Testing PyTorch GPU availability..."
python3 -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CUDA version: {torch.version.cuda}')
if torch.cuda.is_available():
    print(f'GPU count: {torch.cuda.device_count()}')
    for i in range(torch.cuda.device_count()):
        print(f'GPU {i}: {torch.cuda.get_device_name(i)}')
        print(f'GPU {i} memory: {torch.cuda.get_device_properties(i).total_memory / 1e9:.1f} GB')
else:
    print('❌ PyTorch cannot access GPU')
    print('Possible causes:')
    print('  1. Container not started with --gpus flag')
    print('  2. CUDA version mismatch')
    print('  3. Missing nvidia-container-toolkit')
"

# Verify environment variables are set
echo "🔍 Verifying environment variables..."
required_vars=("TOOL" "SUBCOMMAND" "CONFIG" "GIT_SHA" "COPY_DATA_TO_LOCAL_DISK")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "⚠️  Warning: $var is not set"
    else
        echo "✅ $var=${!var}"
    fi
done

echo "🎉 Batch setup completed successfully!"
