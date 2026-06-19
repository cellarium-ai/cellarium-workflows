process INCREMENTAL_PCA_PLUS_PREDICTION {
    publishDir "${params.run_outdir}/pca/", mode: 'copy'

    input:
    val  fit_dataset_dir
    val  predict_dataset_dir
    path onepass_csv
    path hvg_csv
    path pca_fit_config
    path pca_predict_config

    output:
    path 'outputs/checkpoints/last.ckpt', emit: final_model
    path 'outputs/predictions/batch*.csv.gz',  emit: pcs
    path 'gpu_metrics.log', optional: true, emit: gpu_metrics
    path 'fit_config.yaml', emit: fit_config_yaml
    path 'predict_config.yaml', emit: predict_config_yaml

    script:
    """
    mkdir -p outputs/checkpoints
    mkdir -p outputs/predictions

    maybe_pip_install.sh "${params.cellarium_ml_ref}"
    _train_dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${fit_dataset_dir}" "${params.smoke_test}")

    ${params.python3_bin} \$(which render_config.py) \
        --patch fit_config.yaml:${pca_fit_config} \
        "dataset_dir=\${_train_dataset_dir}" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca fit -c fit_config.yaml

    if [ "${predict_dataset_dir}" != "${fit_dataset_dir}" ]; then
        rm -r \${_train_dataset_dir}  # remove training dataset before staging prediction dataset
        _predict_dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${predict_dataset_dir}" "${params.smoke_test}")
    else
        _predict_dataset_dir=\${_train_dataset_dir}
    fi

    ${params.python3_bin} \$(which render_config.py) \
        --patch predict_config.yaml:${pca_predict_config} \
        "dataset_dir=\${_predict_dataset_dir}" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca predict -c predict_config.yaml
    """
}
