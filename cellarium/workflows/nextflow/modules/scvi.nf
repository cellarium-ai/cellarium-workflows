process SCVI {
    publishDir "${params.run_outdir}/scvi/", mode: 'copy'

    input:
    val  dataset_dir
    path hvg_csv
    path scvi_config

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
        --patch run_config.yaml:${scvi_config} \
        "dataset_dir=\${_dataset_dir}" \
        "hvg_csv=./${hvg_csv}"

    run_with_gpu_monitor.sh cellarium-ml scvi fit -c run_config.yaml
    """
}
