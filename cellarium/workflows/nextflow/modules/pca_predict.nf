process INCREMENTAL_PCA_PREDICT {
    publishDir "${params.outdir}/pca/predictions/", mode: 'copy'

    input:
    val  dataset_dir
    path pca_model
    path onepass_csv
    path hvg_csv
    path base_yaml

    output:
    // grab all the output files
    path 'outputs/predictions/batch*.csv.gz', emit: pcs

    script:
    """
    mkdir -p outputs/predictions

    if ${params.gcp_download}; then
        mkdir -p /tmp/dataset
        gcloud storage cp --quiet '${dataset_dir}/*.h5ad' /tmp/dataset/
        _dataset_dir=/tmp/dataset
    else
        _dataset_dir='${dataset_dir}'
    fi

    ${params.python3_bin} \$(which render_config.py) ${base_yaml} \
        "dataset_dir=\${_dataset_dir}" \
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
