#!/usr/bin/env python3
"""Test script to verify the shared components work correctly."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from shared_components import (
    get_pytorch_setup_code,
    get_git_install_code,
    get_data_download_code,
    get_cellarium_cli_code,
    get_current_google_user,
    get_allowed_cli_tool_names,
    create_train_op_function,
    get_train_op_code,
)

def test_code_generation():
    """Test that all code generation functions work."""
    print("Testing code generation functions...")
    
    # Test git install code
    git_code = get_git_install_code()
    print(f"Git install code length: {len(git_code)}")
    assert "pip install" in git_code
    assert "cellarium-ml" in git_code
    
    # Test pytorch setup code
    pytorch_code = get_pytorch_setup_code()
    print(f"PyTorch setup code length: {len(pytorch_code)}")
    assert "psutil" in pytorch_code
    assert "torch" in pytorch_code
    assert "OMP_NUM_THREADS" in pytorch_code
    
    # Test data download code
    data_code = get_data_download_code()
    print(f"Data download code length: {len(data_code)}")
    assert "gcsfs" in data_code
    assert "download_file" in data_code
    
    # Test cellarium CLI code
    cli_code = get_cellarium_cli_code()
    print(f"Cellarium CLI code length: {len(cli_code)}")
    assert "cellarium_ml_cli" in cli_code
    
    print("All code generation tests passed!")

def test_train_op_functions():
    """Test train_op function creation and code generation."""
    print("Testing train_op functions...")
    
    # Test creating train_op function
    train_op = create_train_op_function(copy_data_to_local_disk=True)
    assert callable(train_op)
    print("✓ create_train_op_function works")
    
    # Test with copy_data_to_local_disk=False
    train_op_no_copy = create_train_op_function(copy_data_to_local_disk=False)
    assert callable(train_op_no_copy)
    print("✓ create_train_op_function works with copy_data_to_local_disk=False")
    
    # Test get_train_op_code
    code_with_download = get_train_op_code(copy_data_to_local_disk=True)
    assert len(code_with_download) > 0
    assert "get_git_install_code" in code_with_download
    assert "get_cellarium_cli_code" in code_with_download
    assert "get_data_download_code" in code_with_download  # Should contain data download code
    print("✓ get_train_op_code works with data download")
    
    code_without_download = get_train_op_code(copy_data_to_local_disk=False)
    assert len(code_without_download) > 0
    assert "get_git_install_code" in code_without_download
    assert "get_cellarium_cli_code" in code_without_download
    assert "get_data_download_code" not in code_without_download  # Should not contain data download code
    print("✓ get_train_op_code works without data download")
    
    print("Train_op function tests passed!")

def test_imports():
    """Test that all workflow files can be imported."""
    print("Testing workflow file imports...")
    
    try:
        import submit_single_component
        print("✓ submit_single_component imports successfully")
    except Exception as e:
        print(f"✗ submit_single_component import failed: {e}")
        raise
    
    try:
        import submit_pipeline
        print("✓ submit_pipeline imports successfully")
    except Exception as e:
        print(f"✗ submit_pipeline import failed: {e}")
        raise
    
    try:
        import local_single_component
        print("✓ local_single_component imports successfully")
    except Exception as e:
        print(f"✗ local_single_component import failed: {e}")
        raise
    
    print("All import tests passed!")

def test_utility_functions():
    """Test utility functions."""
    print("Testing utility functions...")
    
    # Test get_current_google_user (may fail if not authenticated)
    try:
        user = get_current_google_user()
        print(f"Current Google user: {user}")
    except Exception as e:
        print(f"Google user test skipped (expected): {e}")
    
    print("Utility function tests completed!")

if __name__ == "__main__":
    test_code_generation()
    test_train_op_functions()
    test_imports()
    test_utility_functions()
    print("All tests completed successfully!")
