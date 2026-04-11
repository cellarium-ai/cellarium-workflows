#!/usr/bin/env nextflow

params.h5ad_bucket = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.output_bucket = 'gs://cellarium-dev-central/workflows/tmp'

params.config_onepass = 'workflows/configs/base_onepass.yaml'
params.config_hvg = 'workflows/configs/base_hvg.yaml'
params.config_pca = 'workflows/configs/base_pca.yaml'

params.container = 'us-central1-docker.pkg.dev/broad-dsde-methods/cellarium-ai/cellarium-ml:0.0.8'

// h5ad files from the extract bucket
dataset_ch = Channel.fromPath(params.h5ad_bucket, type: 'dir')

// config files
cfg_onepass_ch = Channel.fromPath(params.config_onepass)
cfg_hvg_ch = Channel.fromPath(params.config_hvg)
cfg_pca_ch = Channel.fromPath(params.config_pca)

process ONEPASS_MEAN_VAR {
    container params.container
    machineType 'n1-standard-16'
    accelerator 1, type: 'nvidia-tesla-t4'
    scratch true
    
    publishDir "${params.output_bucket}/onepass_mean_var_std/", mode: 'copy'

    input:
    path local_dataset
    path base_yaml

    output:
    path 'outputs/checkpoints/onepass_mean_var_std.ckpt', emit: checkpoint

    script:
    """
    # 1. Create the outputs directory to ensure it exists
    mkdir -p outputs/checkpoints

    # 2. Inject the local dataset path into the YAML
    # We use sed to replace __DATASET_GLOB__ with the local path + wildcard
    sed "s|__DATASET_GLOB__|./${local_dataset}/*.h5ad|g" ${base_yaml} > run_config.yaml

    # 3. Run the model
    cellarium-ml onepass_mean_var fit -c run_config.yaml
    """
}

process HIGHLY_VARIABLE_GENES {
    container params.container
    machineType 'n1-standard-16'
    accelerator 1, type: 'nvidia-tesla-t4'
    scratch true

    publishDir "${params.output_bucket}/hvg_seurat_v3/", mode: 'copy'

    input:
    path local_dataset
    path base_yaml

    output:
    // Assuming HVGSeuratV3 writes this CSV to the root_dir (outputs)
    path 'outputs/*.csv', emit: hvg_csv

    script:
    """
    mkdir -p outputs
    
    sed "s|__DATASET_GLOB__|./${local_dataset}/*.h5ad|g" ${base_yaml} > run_config.yaml

    cellarium-ml highly_variable_genes fit -c run_config.yaml
    """
}

process INCREMENTAL_PCA {
    container params.container
    machineType 'n1-standard-16'
    accelerator 1, type: 'nvidia-tesla-t4'
    scratch true

    // This is the grand finale output we care about
    publishDir "${params.output_bucket}/pca/", mode: 'copy'

    input:
    path local_dataset
    path onepass_ckpt
    path hvg_csv
    path base_yaml

    output:
    // Capture the final PCA model checkpoint
    path 'outputs/checkpoints/pca_final.ckpt', emit: final_model

    script:
    """
    mkdir -p outputs/checkpoints
    
    # We chain sed commands to replace all three placeholders dynamically.
    # Notice we point directly to the localized files that Nextflow staged for us.
    sed -e "s|__DATASET_GLOB__|./${local_dataset}/*.h5ad|g" \
        -e "s|__ONEPASS_CKPT__|./${onepass_ckpt}|g" \
        -e "s|__HVG_CSV__|./${hvg_csv}|g" \
        ${base_yaml} > run_config.yaml

    cellarium-ml incremental_pca fit -c run_config.yaml
    """
}

workflow {
    // in parallel
    onepass_out = ONEPASS_MEAN_VAR(dataset_ch, cfg_onepass_ch)
    hvg_out = HIGHLY_VARIABLE_GENES(dataset_ch, cfg_hvg_ch)

    // waits for both outputs
    INCREMENTAL_PCA(
        dataset_ch, 
        onepass_out.checkpoint, 
        hvg_out.hvg_csv, 
        cfg_pca_ch
    )
}
