process INCREMENTAL_PCA_PLUS_PREDICTION {
    publishDir "${params.outdir}/pca/", mode: 'copy'

    input:
    val  dataset_dir
    path onepass_csv
    path hvg_csv
    path base_yaml
    path base_predict_yaml

    output:
    path 'outputs/checkpoints/pca_final.ckpt', emit: final_model
    path 'outputs/predictions/batch*.csv.gz',  emit: pcs
    path 'gpu_metrics.log', optional: true, emit: gpu_metrics

    script:
    """
    mkdir -p outputs/checkpoints
    mkdir -p outputs/predictions

    if ${params.gcp_download}; then
        mkdir -p /tmp/dataset
        gcloud storage cp '${dataset_dir}/*.h5ad' /tmp/dataset/
        _dataset_dir=/tmp/dataset
    else
        _dataset_dir='${dataset_dir}'
    fi

    ${params.python3_bin} \$(which render_config.py) ${base_yaml} \
        "dataset_dir=\${_dataset_dir}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "var_names_key=${params.var_names_key}" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}" \
        "max_cache_size=${params.max_cache_size}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca fit -c run_config.yaml

    ${params.python3_bin} \$(which render_config.py) ${base_predict_yaml} \
        "dataset_dir=\${_dataset_dir}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "var_names_key=${params.var_names_key}" \
        "pca_model=outputs/checkpoints/pca_final.ckpt" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}" \
        "max_cache_size=${params.max_cache_size}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca predict -c run_config.yaml
    """
}
