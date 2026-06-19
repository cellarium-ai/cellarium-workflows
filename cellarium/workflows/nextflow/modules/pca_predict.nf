process INCREMENTAL_PCA_PREDICT {
    publishDir "${params.run_outdir}/pca/predictions/", mode: 'copy'

    input:
    val  dataset_dir
    path pca_model
    path onepass_csv
    path hvg_csv
    path pca_predict_config

    output:
    // grab all the output files
    path 'outputs/predictions/batch*.csv.gz', emit: pcs
    path 'gpu_metrics.log', optional: true, emit: gpu_metrics
    path 'run_config.yaml', emit: config_yaml

    script:
    """
    mkdir -p outputs/predictions

    maybe_pip_install.sh "${params.cellarium_ml_ref}"
    _dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${dataset_dir}" "${params.smoke_test}")

    ${params.python3_bin} \$(which render_config.py) \
        --patch run_config.yaml:${pca_predict_config} \
        "dataset_dir=\${_dataset_dir}" \
        "pca_model=./${pca_model}" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca predict -c run_config.yaml
    """
}
