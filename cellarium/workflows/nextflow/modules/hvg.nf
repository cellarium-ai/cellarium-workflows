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

    DATASET_GLOB=\$(${params.python3_bin} -c "import os; d='./${local_dataset}'; stems=sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith('.h5ad')); print(d + ('/{' + ','.join(stems) + '}.h5ad' if len(stems) != 1 else '/' + stems[0] + '.h5ad'))")

    ${params.python3_bin} \$(which render_config.py) ${base_yaml} \
        "dataset_glob=\${DATASET_GLOB}" \
        "shard_size=${params.shard_size}" \
        "last_shard_size=${params.last_shard_size}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "n_top_genes=${params.n_top_genes}" \
        "flavor=${params.flavor}" \
        "batch_index_n=${params.batch_index_n}"

    cellarium-ml hvg_seurat_v3 fit -c run_config.yaml
    """
}
