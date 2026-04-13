process INCREMENTAL_PCA {
    publishDir "${params.outdir}/pca/", mode: 'copy'

    input:
    path local_dataset
    path onepass_csv
    path hvg_csv
    path base_yaml

    output:
    path 'outputs/checkpoints/pca_final.ckpt', emit: final_model

    script:
    """
    mkdir -p outputs/checkpoints

    ${params.python3_bin} \$(which render_config.py) ${base_yaml} \
        "dataset_dir=./${local_dataset}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "var_names_key=${params.var_names_key}" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}"

    cellarium-ml incremental_pca fit -c run_config.yaml
    """
}
