process INCREMENTAL_PCA {
    publishDir "${params.outdir}/pca/", mode: 'copy'

    input:
    val  dataset_dir
    path onepass_csv
    path hvg_csv
    path base_yaml

    output:
    path 'outputs/checkpoints/last.ckpt', emit: final_model
    path 'gpu_metrics.log', optional: true, emit: gpu_metrics

    script:
    """
    mkdir -p outputs/checkpoints

    maybe_pip_install.sh "${params.cellarium_ml_ref}"
    _dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${dataset_dir}")

    ${params.python3_bin} \$(which render_config.py) ${base_yaml} \
        "dataset_dir=\${_dataset_dir}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "use_pflogpf=${params.use_pflogpf}" \
        "apply_normalize_total=${params.apply_normalize_total}" \
        "target_count=${params.target_count}" \
        "apply_log1p=${params.apply_log1p}" \
        "zscore_genes=${params.zscore_genes}" \
        "var_names_key=${params.var_names_key}" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}" \
        "max_cache_size=${params.max_cache_size}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca fit -c run_config.yaml
    """
}
