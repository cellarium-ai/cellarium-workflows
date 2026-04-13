process HIGHLY_VARIABLE_GENES {
    publishDir "${params.outdir}/hvg_seurat_v3/", mode: 'copy'

    input:
    path local_dataset
    path base_yaml

    output:
    path 'outputs/*.csv', emit: hvg_csv

    script:
    """
    mkdir -p outputs

    render_config.py ${base_yaml} \
        "dataset_glob=./${local_dataset}/*.h5ad" \
        "n_top_genes=${params.n_top_genes}" \
        "flavor=${params.flavor}" \
        "batch_index_n=${params.batch_index_n}"

    cellarium-ml highly_variable_genes fit -c run_config.yaml
    """
}
