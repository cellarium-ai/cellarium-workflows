process INCREMENTAL_PCA_PLUS_PREDICTION {
    publishDir "${params.outdir}/pca/", mode: 'copy'

    input:
    val  fit_dataset_dir
    val  predict_dataset_dir
    path onepass_csv
    path hvg_csv
    path base_fit_yaml
    path base_predict_yaml

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
    _train_dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${fit_dataset_dir}")

    ${params.python3_bin} \$(which render_config.py) ${base_fit_yaml} \
        "dataset_dir=\${_train_dataset_dir}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "var_names_key=${params.var_names_key}" \
        "apply_normalize_total=${params.apply_normalize_total}" \
        "target_count=${params.target_count}" \
        "apply_log1p=${params.apply_log1p}" \
        "use_pflogpf=${params.use_pflogpf}" \
        "zscore_genes=${params.zscore_genes}" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}" \
        "max_cache_size=${params.max_cache_size}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca fit -c run_config.yaml
    cp run_config.yaml fit_config.yaml

    if [ "${predict_dataset_dir}" != "${fit_dataset_dir}" ]; then
        rm -r \${_train_dataset_dir}  # remove training dataset before staging prediction dataset
        _predict_dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${predict_dataset_dir}")
    else
        _predict_dataset_dir=\${_train_dataset_dir}
    fi

    ${params.python3_bin} \$(which render_config.py) ${base_predict_yaml} \
        "dataset_dir=\${_predict_dataset_dir}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "var_names_key=${params.var_names_key}" \
        "apply_normalize_total=${params.apply_normalize_total}" \
        "target_count=${params.target_count}" \
        "apply_log1p=${params.apply_log1p}" \
        "use_pflogpf=${params.use_pflogpf}" \
        "zscore_genes=${params.zscore_genes}" \
        "pca_model=outputs/checkpoints/last.ckpt" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}" \
        "max_cache_size=${params.max_cache_size}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca predict -c run_config.yaml
    cp run_config.yaml predict_config.yaml
    """
}
