process INCREMENTAL_PCA_PREDICT {
    publishDir "${params.outdir}/pca/predictions/", mode: 'copy'

    input:
    path local_dataset
    path pca_model
    path onepass_csv
    path hvg_csv
    path base_yaml

    output:
    // grab all the output files
    path 'outputs/predictions/batch*.csv.gz', emit: pcs

    script:
    """
    mkdir -p outputs/predictions/

    DATASET_GLOB=\$(${params.python3_bin} -c "import os; d='./${local_dataset}'; stems=sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith('.h5ad')); print(d + ('/{' + ','.join(stems) + '}.h5ad' if len(stems) != 1 else '/' + stems[0] + '.h5ad'))")

    ${params.python3_bin} \$(which render_config.py) ${base_yaml} \
        "dataset_glob=\${DATASET_GLOB}" \
        "shard_size=${params.shard_size}" \
        "last_shard_size=${params.last_shard_size}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "var_names_key=${params.var_names_key}" \
        "pca_model=./${pca_model}" \
        "onepass_csv=./${onepass_csv}" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}"

    cellarium-ml incremental_pca predict -c run_config.yaml
    """
}
