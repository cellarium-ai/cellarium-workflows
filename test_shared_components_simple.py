#!/usr/bin/env python3
"""
Test script to verify that the train_op code generation works correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cellarium', 'workflows'))

def test_train_op_code_generation():
    """Test that we can generate the train_op code without errors."""
    print("Testing train_op code generation...")
    
    try:
        from shared_components import get_train_op_code
        
        # Test with copy_data_to_local_disk=True
        code_with_data = get_train_op_code(copy_data_to_local_disk=True)
        print("✅ Generated code with data download")
        print(f"Code length: {len(code_with_data)} characters")
        
        # Test with copy_data_to_local_disk=False
        code_without_data = get_train_op_code(copy_data_to_local_disk=False)
        print("✅ Generated code without data download")
        print(f"Code length: {len(code_without_data)} characters")
        
        # Verify the code looks reasonable
        if 'import' in code_with_data and 'def' not in code_with_data:
            print("✅ Code appears to be inline script code (no function definitions)")
        else:
            print("⚠️  Code structure might be unexpected")
            
        return True
    except Exception as e:
        print(f"❌ Code generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_train_op_function_creation():
    """Test that we can create the train_op function for local execution."""
    print("\nTesting local train_op function creation...")
    
    try:
        from shared_components import create_train_op_function
        
        # Create the function
        train_op_func = create_train_op_function(copy_data_to_local_disk=False)
        print("✅ Created train_op function")
        print(f"Function type: {type(train_op_func)}")
        print(f"Function name: {train_op_func.__name__}")
        
        # Check the function signature
        import inspect
        sig = inspect.signature(train_op_func)
        print(f"✅ Function signature: {sig}")
        
        return True
    except Exception as e:
        print(f"❌ Function creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_script_loading():
    """Test that individual scripts can be loaded."""
    print("\nTesting individual script loading...")
    
    try:
        from shared_components import (
            get_git_install_code,
            get_pytorch_setup_code, 
            get_data_download_code,
            get_cellarium_cli_code
        )
        
        scripts = [
            ("git_install", get_git_install_code),
            ("pytorch_setup", get_pytorch_setup_code),
            ("data_download", get_data_download_code),
            ("cellarium_cli", get_cellarium_cli_code),
        ]
        
        for script_name, loader_func in scripts:
            code = loader_func()
            print(f"✅ Loaded {script_name}: {len(code)} characters")
            
        return True
    except Exception as e:
        print(f"❌ Script loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running shared components tests...\n")
    
    success1 = test_script_loading()
    success2 = test_train_op_code_generation()
    success3 = test_train_op_function_creation()
    
    if success1 and success2 and success3:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)
