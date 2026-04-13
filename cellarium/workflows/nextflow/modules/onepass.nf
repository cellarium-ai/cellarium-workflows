process ONEPASS_MEAN_VAR {
    publishDir "${params.outdir}/onepass_mean_var_std/", mode: 'copy'

    input:
    path local_dataset
    path base_yaml

    output:
    path 'outputs/onepass_mean_var_std.csv', emit: onepass_csv

    script:
    """
    mkdir -p outputs

    ${params.python3_bin} \$(which render_config.py) ${base_yaml} \
        "dataset_dir=./${local_dataset}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "var_names_key=${params.var_names_key}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}"

    cellarium-ml onepass_mean_var_std fit -c run_config.yaml
    """
}
