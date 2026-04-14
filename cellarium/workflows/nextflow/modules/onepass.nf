process ONEPASS_MEAN_VAR {
    publishDir "${params.outdir}/onepass_mean_var_std/", mode: 'copy'

    input:
    val  dataset_dir
    path base_yaml

    output:
    path 'outputs/onepass_mean_var_std.csv', emit: onepass_csv
    path 'gpu_metrics.log', optional: true, emit: gpu_metrics

    script:
    """
    mkdir -p outputs

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
        "var_names_key=${params.var_names_key}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "max_cache_size=${params.max_cache_size}"

    run_with_gpu_monitor.sh cellarium-ml onepass_mean_var_std fit -c run_config.yaml
    """
}
