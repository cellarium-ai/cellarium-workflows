process INCREMENTAL_PCA {
    publishDir "${params.run_outdir}/pca/", mode: 'copy'

    input:
    val  dataset_dir
    path onepass_csv
    path hvg_csv
    path pca_fit_config

    output:
    path 'outputs/checkpoints/last.ckpt', emit: final_model
    path 'gpu_metrics.log', optional: true, emit: gpu_metrics
    path 'run_config.yaml', emit: config_yaml

    script:
    """
    mkdir -p outputs/checkpoints

    maybe_pip_install.sh "${params.cellarium_ml_ref}"
    _dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${dataset_dir}" "${params.smoke_test}")

    ${params.python3_bin} \$(which render_config.py) \
        --patch run_config.yaml:${pca_fit_config} \
        "dataset_dir=\${_dataset_dir}" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca fit -c run_config.yaml
    """
}
