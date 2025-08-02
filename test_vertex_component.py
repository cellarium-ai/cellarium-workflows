#!/usr/bin/env python3
"""
Test script to verify that the Vertex AI component creation works correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cellarium', 'workflows'))

from shared_components import create_vertex_ai_train_op_component

def test_component_creation():
    """Test that we can create a component without errors."""
    print("Testing Vertex AI component creation...")
    
    try:
        # This should not raise any errors
        train_op_component = create_vertex_ai_train_op_component(
            base_image="test-image"
        )
        print("✅ Component created successfully")
        print(f"Component type: {type(train_op_component)}")
        
        # Check if it has a name attribute (might be different for KFP components)
        if hasattr(train_op_component, '__name__'):
            print(f"Component name: {train_op_component.__name__}")
        elif hasattr(train_op_component, 'name'):
            print(f"Component name: {train_op_component.name}")
        elif hasattr(train_op_component, 'component_spec') and hasattr(train_op_component.component_spec, 'name'):
            print(f"Component name: {train_op_component.component_spec.name}")
        else:
            print("Component name: <no name attribute found>")
        
        return True
    except Exception as e:
        print(f"❌ Component creation failed: {e}")
        return False

def test_component_inspection():
    """Test that we can inspect the created component."""
    print("\nTesting component inspection...")
    
    try:
        train_op_component = create_vertex_ai_train_op_component(
            base_image="test-image"
        )
        
        # Check if it has the expected attributes
        if hasattr(train_op_component, 'component_spec'):
            print("✅ Component has component_spec attribute")
        else:
            print("⚠️  Component missing component_spec attribute")
            
        # Try to get the function signature
        import inspect
        sig = inspect.signature(train_op_component)
        print(f"✅ Component signature: {sig}")
        
        return True
    except Exception as e:
        print(f"❌ Component inspection failed: {e}")
        return False

if __name__ == "__main__":
    print("Running Vertex AI component tests...\n")
    
    success1 = test_component_creation()
    success2 = test_component_inspection()
    
    if success1 and success2:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)
