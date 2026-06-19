process SEURAT_V3_HIGHLY_VARIABLE_GENES {
    publishDir "${params.run_outdir}/hvg_seurat_v3/", mode: 'copy'

    input:
    val  dataset_dir
    path seurat_v3_hvg_config

    output:
    path 'outputs/hvg_genes__top*__hvg_only.csv', emit: hvg_csv
    path 'gpu_metrics.log', optional: true, emit: gpu_metrics
    path 'run_config.yaml', emit: config_yaml

    script:
    """
    mkdir -p outputs

    maybe_pip_install.sh "${params.cellarium_ml_ref}"
    _dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${dataset_dir}" "${params.smoke_test}")

    ${params.python3_bin} \$(which render_config.py) \
        --patch run_config.yaml:${seurat_v3_hvg_config} \
        "dataset_dir=\${_dataset_dir}"

    run_with_gpu_monitor.sh cellarium-ml hvg_seurat_v3 fit -c run_config.yaml
    """
}
