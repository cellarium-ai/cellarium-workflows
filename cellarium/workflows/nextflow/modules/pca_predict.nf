process INCREMENTAL_PCA_PREDICT {
    publishDir "${params.outdir}/pca/predictions/", mode: 'copy'

    input:
    path local_dataset
    path pca_model
    path onepass_ckpt
    path hvg_csv
    path base_yaml

    output:
    // grab all the output files
    path 'outputs/batch*.csv.gz', emit: pcs

    script:
    """
    mkdir -p outputs/

    render_config.py ${base_yaml} \
        "dataset_glob=./${local_dataset}/*.h5ad" \
        "pca_model=./${pca_model}" \
        "onepass_ckpt=./${onepass_ckpt}" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}"

    cellarium-ml incremental_pca predict -c run_config.yaml
    """
}
