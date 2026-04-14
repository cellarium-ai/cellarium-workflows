process HIGHLY_VARIABLE_GENES {
    publishDir "${params.outdir}/hvg_seurat_v3/", mode: 'copy'

    input:
    val  dataset_dir
    path base_yaml

    output:
    path 'outputs/hvg_genes__top*__hvg_only.csv', emit: hvg_csv
    path 'gpu_metrics.log', optional: true, emit: gpu_metrics

    script:
    """
    mkdir -p outputs

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
        "n_top_genes=${params.n_top_genes}" \
        "flavor=${params.flavor}" \
        "batch_index_n=${params.batch_index_n}" \
        "var_names_key=${params.var_names_key}"

    run_with_gpu_monitor.sh cellarium-ml hvg_seurat_v3 fit -c run_config.yaml
    """
}
