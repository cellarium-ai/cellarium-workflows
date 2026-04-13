process INCREMENTAL_PCA {
    publishDir "${params.outdir}/pca/", mode: 'copy'

    input:
    path local_dataset
    path onepass_ckpt
    path hvg_csv
    path base_yaml

    output:
    path 'outputs/checkpoints/pca_final.ckpt', emit: final_model

    script:
    """
    mkdir -p outputs/checkpoints

    render_config.py ${base_yaml} \
        "dataset_glob=./${local_dataset}/*.h5ad" \
        "onepass_ckpt=./${onepass_ckpt}" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}"

    cellarium-ml incremental_pca fit -c run_config.yaml
    """
}
