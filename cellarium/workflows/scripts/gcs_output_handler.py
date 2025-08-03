"""GCS output handling for batch jobs."""
import os
import tempfile
import gcsfs
import yaml
import re
from pathlib import Path
from typing import Dict, Any, Optional


def detect_gcs_paths_in_config(config_path: str) -> Dict[str, str]:
    """
    Parse config file and detect GCS output paths.
    
    Returns:
        Dictionary mapping local paths to GCS paths
    """
    gcs_paths = {}
    
    try:
        # Load the config file
        if config_path.startswith('gs://'):
            fs = gcsfs.GCSFileSystem()
            with fs.open(config_path, 'r') as f:
                config_content = f.read()
        else:
            with open(config_path, 'r') as f:
                config_content = f.read()
        
        # Find all /gcs/ paths in the config
        gcs_pattern = r'/gcs/([^/\s]+)(/[^\s]*)?'
        matches = re.findall(gcs_pattern, config_content)
        
        for bucket, path in matches:
            full_gcs_path = f"/gcs/{bucket}{path}"
            gcs_url = f"gs://{bucket}{path}"
            
            # Create a local temporary directory for this path
            local_dir = f"/tmp/gcs_output/{bucket}{path}"
            gcs_paths[full_gcs_path] = gcs_url
            
        return gcs_paths
    except Exception as e:
        print(f"Warning: Could not parse config for GCS paths: {e}")
        return {}


def setup_gcs_output_directories(gcs_paths: Dict[str, str]) -> Dict[str, str]:
    """
    Create local directories for GCS output paths.
    
    Returns:
        Dictionary mapping original GCS paths to local paths
    """
    path_mapping = {}
    
    for gcs_path, gcs_url in gcs_paths.items():
        # Create local directory
        local_path = f"/tmp/gcs_output{gcs_path[4:]}"  # Remove /gcs prefix
        os.makedirs(local_path, exist_ok=True)
        path_mapping[gcs_path] = local_path
        print(f"Mapped {gcs_path} -> {local_path} (will sync to {gcs_url})")
    
    return path_mapping


def update_config_with_local_paths(config_path: str, path_mapping: Dict[str, str]) -> str:
    """
    Update config file to use local paths instead of GCS paths.
    
    Returns:
        Path to the updated config file
    """
    try:
        # Load the config
        if config_path.startswith('gs://'):
            fs = gcsfs.GCSFileSystem()
            with fs.open(config_path, 'r') as f:
                config_content = f.read()
        else:
            with open(config_path, 'r') as f:
                config_content = f.read()
        
        # Replace GCS paths with local paths
        updated_content = config_content
        for gcs_path, local_path in path_mapping.items():
            updated_content = updated_content.replace(gcs_path, local_path)
        
        # Write updated config to local file
        local_config_path = "/tmp/config_with_local_paths.yaml"
        with open(local_config_path, 'w') as f:
            f.write(updated_content)
        
        print(f"Updated config saved to {local_config_path}")
        return local_config_path
        
    except Exception as e:
        print(f"Warning: Could not update config paths: {e}")
        return config_path


def sync_outputs_to_gcs(gcs_paths: Dict[str, str], path_mapping: Dict[str, str]):
    """
    Sync local output directories back to GCS.
    """
    fs = gcsfs.GCSFileSystem()
    
    for gcs_path, gcs_url in gcs_paths.items():
        local_path = path_mapping.get(gcs_path)
        if not local_path or not os.path.exists(local_path):
            print(f"Skipping {gcs_path}: local path {local_path} not found")
            continue
        
        try:
            print(f"Syncing {local_path} to {gcs_url}")
            
            # Upload all files in the local directory
            for root, dirs, files in os.walk(local_path):
                for file in files:
                    local_file = os.path.join(root, file)
                    
                    # Calculate relative path and GCS destination
                    rel_path = os.path.relpath(local_file, local_path)
                    gcs_file = f"{gcs_url.rstrip('/')}/{rel_path}"
                    
                    # Ensure parent directory exists in GCS
                    gcs_dir = '/'.join(gcs_file.split('/')[:-1])
                    fs.makedirs(gcs_dir, exist_ok=True)
                    
                    # Upload file
                    fs.put(local_file, gcs_file)
                    print(f"  Uploaded {rel_path}")
            
            print(f"✅ Successfully synced {local_path} to {gcs_url}")
            
        except Exception as e:
            print(f"❌ Failed to sync {local_path} to {gcs_url}: {e}")


def setup_gcs_output_handling(config_path: str) -> str:
    """
    Main function to set up GCS output handling.
    
    Returns:
        Updated config path with local directories
    """
    print("Setting up GCS output handling...")
    
    # Detect GCS paths in config
    gcs_paths = detect_gcs_paths_in_config(config_path)
    
    if not gcs_paths:
        print("No GCS output paths detected in config")
        return config_path
    
    print(f"Detected {len(gcs_paths)} GCS output paths:")
    for gcs_path, gcs_url in gcs_paths.items():
        print(f"  {gcs_path} -> {gcs_url}")
    
    # Set up local directories
    path_mapping = setup_gcs_output_directories(gcs_paths)
    
    # Update config file
    updated_config_path = update_config_with_local_paths(config_path, path_mapping)
    
    # Store paths for later syncing
    with open("/tmp/gcs_sync_info.yaml", "w") as f:
        yaml.dump({
            'gcs_paths': gcs_paths,
            'path_mapping': path_mapping
        }, f)
    
    return updated_config_path


def finalize_gcs_output_sync():
    """
    Final step: sync all outputs back to GCS.
    """
    try:
        print("Finalizing GCS output sync...")
        
        # Load sync info
        with open("/tmp/gcs_sync_info.yaml", "r") as f:
            sync_info = yaml.safe_load(f)
        
        gcs_paths = sync_info.get('gcs_paths', {})
        path_mapping = sync_info.get('path_mapping', {})
        
        if gcs_paths:
            sync_outputs_to_gcs(gcs_paths, path_mapping)
        else:
            print("No GCS paths to sync")
            
    except Exception as e:
        print(f"Warning: Could not finalize GCS sync: {e}")
