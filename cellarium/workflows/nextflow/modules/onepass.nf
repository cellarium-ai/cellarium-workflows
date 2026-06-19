process ONEPASS_MEAN_VAR {
    publishDir "${params.run_outdir}/onepass_mean_var_std/", mode: 'copy'

    input:
    val  dataset_dir
    path onepass_config

    output:
    path 'outputs/onepass_mean_var_std.csv', emit: onepass_csv
    path 'gpu_metrics.log', optional: true, emit: gpu_metrics
    path 'run_config.yaml', emit: config_yaml

    script:
    """
    mkdir -p outputs

    maybe_pip_install.sh "${params.cellarium_ml_ref}"
    _dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${dataset_dir}" "${params.smoke_test}")

    ${params.python3_bin} \$(which render_config.py) \
        --patch run_config.yaml:${onepass_config} \
        "dataset_dir=\${_dataset_dir}"

    run_with_gpu_monitor.sh cellarium-ml onepass_mean_var_std fit -c run_config.yaml
    """
}
