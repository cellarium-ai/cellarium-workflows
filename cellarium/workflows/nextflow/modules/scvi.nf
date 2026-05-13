process SCVI {
    publishDir "${params.outdir}/scvi/", mode: 'copy'

    input:
    val  dataset_dir
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
        "var_names_key=${params.var_names_key}" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}" \
        "max_cache_size=${params.max_cache_size}" \
        "batch_key=${params.batch_key}" \
        "categorical_covariate_keys=${params.categorical_covariate_keys}" \
        "n_latent=${params.n_latent}"

    run_with_gpu_monitor.sh cellarium-ml scvi fit -c run_config.yaml
    """
}
