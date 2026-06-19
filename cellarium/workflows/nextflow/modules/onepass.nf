process ONEPASS_MEAN_VAR {
    publishDir "${params.outdir}/onepass_mean_var_std/", mode: 'copy'

    input:
    val  dataset_dir
    path base_yaml

    output:
    path 'outputs/onepass_mean_var_std.csv', emit: onepass_csv
    path 'gpu_metrics.log', optional: true, emit: gpu_metrics
    path 'run_config.yaml', emit: config_yaml

    script:
    """
    mkdir -p outputs

    maybe_pip_install.sh "${params.cellarium_ml_ref}"
    _dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${dataset_dir}")

    ${params.python3_bin} \$(which render_config.py) ${base_yaml} \
        "dataset_dir=\${_dataset_dir}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "var_names_key=${params.var_names_key}" \
        "total_mrna_umis_key=${params.total_mrna_umis_key}" \
        "apply_normalize_total=${params.apply_normalize_total}" \
        "target_count=${params.target_count}" \
        "apply_log1p=${params.apply_log1p}" \
        "use_pflogpf=${params.use_pflogpf}" \
        "sparse_dataloader=${params.sparse_dataloader}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "max_cache_size=${params.max_cache_size}"

    run_with_gpu_monitor.sh cellarium-ml onepass_mean_var_std fit -c run_config.yaml
    """
}
