process ONEPASS_HVG_INCREMENTAL_PCA_PLUS_PREDICTION {
    publishDir "${params.outdir}/pca/", mode: 'copy'

    input:
    val  fit_dataset_dir
    val  predict_dataset_dir
    val  hvg_method
    path base_onepass_yaml
    path base_seurat_v3_hvg_yaml
    path base_pca_fit_yaml
    path base_pca_predict_yaml

    output:
    path 'outputs/checkpoints/last.ckpt', emit: final_model
    path 'outputs/predictions/batch*.csv.gz',  emit: pcs
    path 'gpu_metrics.log', optional: true, emit: gpu_metrics
    path 'onepass_config.yaml', emit: onepass_config_yaml
    path 'seurat_v3_hvg_config.yaml', optional: true, emit: seurat_v3_hvg_config_yaml
    path 'outputs/seurat_hvgs.csv', emit: seurat_hvg_csv
    path 'outputs/kotliar_hvgs.csv', emit: kotliar_hvg_csv
    path 'outputs/seurat_v3_hvg_genes__top${params.n_top_genes}__hvg_only.csv', optional: true, emit: seurat_v3_hvg_csv
    path 'pca_fit_config.yaml', emit: pca_fit_config_yaml
    path 'pca_predict_config.yaml', emit: pca_predict_config_yaml

    script:
    """
    if [[ "${hvg_method}" != "seurat_v3" && "${hvg_method}" != "seurat" && "${hvg_method}" != "kotliar" ]]; then
        echo "Error: hvg_method must be one of ['seurat_v3', 'seurat', 'kotliar']"
        exit 1
    fi

    mkdir -p outputs/checkpoints
    mkdir -p outputs/predictions

    maybe_pip_install.sh "${params.cellarium_ml_ref}"

    echo "Staging training dataset..."
    _train_dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${fit_dataset_dir}")

    echo "Rendering onepass config file..."
    ${params.python3_bin} \$(which render_config.py) ${base_onepass_yaml} \
        "dataset_dir=\${_train_dataset_dir}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "var_names_key=${params.var_names_key}" \
        "total_mrna_umis_key=${params.total_mrna_umis_key}" \
        "apply_normalize_total=${params.apply_normalize_total}" \
        "target_count=${params.target_count}" \
        "apply_log1p=${params.apply_log1p}" \
        "use_pflogpf=${params.use_pflogpf}" \
        "sparse_dataloader=${params.sparse_dataloader}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "max_cache_size=${params.max_cache_size}"

    echo "Running onepass_mean_var_std..."
    run_with_gpu_monitor.sh cellarium-ml onepass_mean_var_std fit -c run_config.yaml
    cp run_config.yaml onepass_config.yaml

    echo "Running HVG gene selection: seurat..."
    ${params.python3_bin} \$(which hvg_helper.py) \
        seurat \
        ${params.n_top_genes} \
        outputs/onepass_mean_var_std.csv \
        --output outputs/seurat_hvgs.csv

    echo "Running HVG gene selection: kotliar..."
    ${params.python3_bin} \$(which hvg_helper.py) \
        kotliar \
        ${params.n_top_genes} \
        outputs/onepass_mean_var_std.csv \
        --output outputs/kotliar_hvgs.csv

    if [ "${hvg_method}" = "seurat_v3" ]; then
        echo "Running HVG gene selection: seurat_v3..."
        ${params.python3_bin} \$(which render_config.py) ${base_seurat_v3_hvg_yaml} \
            "dataset_dir=\${_train_dataset_dir}" \
            "num_workers=${params.num_workers}" \
            "prefetch_factor=${params.prefetch_factor}" \
            "accelerator=${params.accelerator}" \
            "batch_size=${params.batch_size}" \
            "n_top_genes=${params.n_top_genes}" \
            "flavor=${params.seurat_v3_flavor}" \
            "batch_index_n=${params.batch_index_n}" \
            "var_names_key=${params.var_names_key}" \
            "max_cache_size=${params.max_cache_size}"

        echo "Running HVG gene selection: seurat_v3..."
        run_with_gpu_monitor.sh cellarium-ml hvg_seurat_v3 fit -c run_config.yaml
        cp run_config.yaml seurat_v3_hvg_config.yaml
        hvg_csv=outputs/hvg_genes__top${params.n_top_genes}__hvg_only.csv
    else
        if [ "${hvg_method}" = "seurat" ]; then
            hvg_csv=outputs/seurat_hvgs.csv
        else
            hvg_csv=outputs/kotliar_hvgs.csv
        fi
    fi

    ${params.python3_bin} \$(which render_config.py) ${base_pca_fit_yaml} \
        "dataset_dir=\${_train_dataset_dir}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "var_names_key=${params.var_names_key}" \
        "apply_normalize_total=${params.apply_normalize_total}" \
        "target_count=${params.target_count}" \
        "apply_log1p=${params.apply_log1p}" \
        "use_pflogpf=${params.use_pflogpf}" \
        "zscore_genes=${params.zscore_genes}" \
        "onepass_csv=outputs/onepass_mean_var_std.csv" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}" \
        "max_cache_size=${params.max_cache_size}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca fit -c run_config.yaml
    cp run_config.yaml pca_fit_config.yaml

    if [ "${predict_dataset_dir}" != "${fit_dataset_dir}" ]; then
        rm -r \${_train_dataset_dir}
        _predict_dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${predict_dataset_dir}")
    else
        _predict_dataset_dir=\${_train_dataset_dir}
    fi

    ${params.python3_bin} \$(which render_config.py) ${base_pca_predict_yaml} \
        "dataset_dir=\${_predict_dataset_dir}" \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "var_names_key=${params.var_names_key}" \
        "apply_normalize_total=${params.apply_normalize_total}" \
        "target_count=${params.target_count}" \
        "apply_log1p=${params.apply_log1p}" \
        "use_pflogpf=${params.use_pflogpf}" \
        "zscore_genes=${params.zscore_genes}" \
        "pca_model=outputs/checkpoints/last.ckpt" \
        "onepass_csv=outputs/onepass_mean_var_std.csv" \
        "hvg_csv=./${hvg_csv}" \
        "n_components=${params.n_components}" \
        "max_cache_size=${params.max_cache_size}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca predict -c run_config.yaml
    cp run_config.yaml pca_predict_config.yaml
    """
}
