#!/usr/bin/env python3
"""
Test script to verify that the Google Batch submission works correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cellarium', 'workflows'))

def test_batch_imports():
    """Test that we can import the batch submission modules."""
    print("Testing Google Batch imports...")
    
    try:
        from submit_batch_component import create_batch_job_spec, submit_batch_component
        print("✅ Single component batch submission imports work")
        
        from submit_batch_pipeline import create_batch_pipeline_jobs, submit_batch_pipeline
        print("✅ Pipeline batch submission imports work")
        
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_batch_job_creation():
    """Test that we can create a batch job spec without errors."""
    print("\nTesting batch job spec creation...")
    
    try:
        from submit_batch_component import create_batch_job_spec
        
        job_spec = create_batch_job_spec(
            job_name="test-job",
            project="test-project",
            location="us-central1",
            tool="test_tool",
            subcommand="fit",
            config="gs://test-bucket/config.yaml",
            git_sha="main",
            copy_data_to_local_disk=True,
            base_image="test-image",
        )
        
        print("✅ Batch job spec created successfully")
        print(f"Task groups: {len(job_spec.task_groups)}")
        print(f"Allocation policy: {job_spec.allocation_policy is not None}")
        print(f"Logs policy: {job_spec.logs_policy is not None}")
        
        return True
    except Exception as e:
        print(f"❌ Batch job spec creation failed: {e}")
        return False

def test_pipeline_jobs_creation():
    """Test that we can create pipeline jobs without errors."""
    print("\nTesting pipeline jobs creation...")
    
    try:
        from submit_batch_pipeline import create_batch_pipeline_jobs
        
        component_definitions = [
            {
                "tool": "test_tool_1",
                "subcommand": "fit",
                "config": "gs://test-bucket/config1.yaml"
            },
            {
                "tool": "test_tool_2", 
                "subcommand": "predict",
                "config": "gs://test-bucket/config2.yaml"
            }
        ]
        
        jobs = create_batch_pipeline_jobs(
            pipeline_name="test-pipeline",
            project="test-project",
            location="us-central1",
            component_definitions=component_definitions,
            copy_data_to_local_disk=True,
            base_image="test-image",
        )
        
        print(f"✅ Created {len(jobs)} pipeline jobs")
        for i, (job_name, job_spec) in enumerate(jobs):
            print(f"  Job {i+1}: {job_name}")
        
        return True
    except Exception as e:
        print(f"❌ Pipeline jobs creation failed: {e}")
        return False

if __name__ == "__main__":
    print("Running Google Batch submission tests...\n")
    
    success1 = test_batch_imports()
    success2 = test_batch_job_creation()
    success3 = test_pipeline_jobs_creation()
    
    if success1 and success2 and success3:
        print("\n🎉 All Google Batch tests passed!")
        print("\nNext steps:")
        print("1. Install google-cloud-batch: pip install google-cloud-batch")
        print("2. Set up authentication: gcloud auth application-default login")
        print("3. Test with a real submission")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)
