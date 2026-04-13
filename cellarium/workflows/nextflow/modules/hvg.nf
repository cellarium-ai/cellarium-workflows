process HIGHLY_VARIABLE_GENES {
    publishDir "${params.outdir}/hvg_seurat_v3/", mode: 'copy'

    input:
    path local_dataset
    path base_yaml

    output:
    path 'outputs/hvg_genes__top*__hvg_only.csv', emit: hvg_csv

    script:
    """
    mkdir -p outputs

    ${params.python3_bin} \$(which render_config.py) ${base_yaml} \
        "dataset_dir=./${local_dataset}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "n_top_genes=${params.n_top_genes}" \
        "flavor=${params.flavor}" \
        "batch_index_n=${params.batch_index_n}" \
        "var_names_key=${params.var_names_key}"

    cellarium-ml hvg_seurat_v3 fit -c run_config.yaml
    """
}
