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

    DATASET_GLOB=\$(${params.python3_bin} -c "import os; d='./${local_dataset}'; stems=sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith('.h5ad')); print(d + ('/{' + ','.join(stems) + '}.h5ad' if len(stems) != 1 else '/' + stems[0] + '.h5ad'))")
    read SHARD_SIZE LAST_SHARD_SIZE <<< \$(infer_shards.py ./${local_dataset})

    ${params.python3_bin} \$(which render_config.py) ${base_yaml} \
        "dataset_glob=\${DATASET_GLOB}" \
        "shard_size=\${SHARD_SIZE}" \
        "last_shard_size=\${LAST_SHARD_SIZE}" \
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
        "dataset_glob=\${DATASET_GLOB}" \
        "shard_size=\${SHARD_SIZE}" \
        "last_shard_size=\${LAST_SHARD_SIZE}" \
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
