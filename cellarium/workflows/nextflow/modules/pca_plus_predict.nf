process INCREMENTAL_PCA_PLUS_PREDICTION {
    publishDir "${params.outdir}/pca/", mode: 'copy'

    input:
    path local_dataset
    path onepass_csv
    path hvg_csv
    path base_yaml
    path base_predict_yaml

    output:
    path 'outputs/checkpoints/pca_final.ckpt', emit: final_model
    path 'outputs/predictions/batch*.csv.gz', emit: pcs

    script:
    """
    mkdir -p outputs/checkpoints
    mkdir -p outputs/predictions

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

    ${params.python3_bin} \$(which render_config.py) ${base_predict_yaml} \
        "dataset_dir=./${local_dataset}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "var_names_key=${params.var_names_key}" \
        "pca_model=outputs/checkpoints/pca_final.ckpt" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}"

    cellarium-ml incremental_pca predict -c run_config.yaml
    """
}
