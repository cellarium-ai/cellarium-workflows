process ONEPASS_HVG_INCREMENTAL_PCA_PLUS_PREDICTION {
    publishDir "${params.run_outdir}/pca/", mode: 'copy'

    input:
    val  fit_dataset_dir
    val  predict_dataset_dir
    val  hvg_method
    path onepass_config
    path pca_fit_config
    path pca_predict_config
    path seurat_v3_hvg_config

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
    mkdir -p outputs/checkpoints
    mkdir -p outputs/predictions

    maybe_pip_install.sh "${params.cellarium_ml_ref}"

    echo "Staging training dataset..."
    _train_dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${fit_dataset_dir}" "${params.smoke_test}")

    echo "Patching and running onepass_mean_var_std..."
    ${params.python3_bin} \$(which render_config.py) \
        --patch onepass_config.yaml:${onepass_config} \
        "dataset_dir=\${_train_dataset_dir}"

    run_with_gpu_monitor.sh cellarium-ml onepass_mean_var_std fit -c onepass_config.yaml

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
        ${params.python3_bin} \$(which render_config.py) \
            --patch seurat_v3_hvg_config.yaml:${seurat_v3_hvg_config} \
            "dataset_dir=\${_train_dataset_dir}"

        run_with_gpu_monitor.sh cellarium-ml hvg_seurat_v3 fit -c seurat_v3_hvg_config.yaml
        hvg_csv=outputs/hvg_genes__top${params.n_top_genes}__hvg_only.csv
    else
        if [ "${hvg_method}" = "seurat" ]; then
            hvg_csv=outputs/seurat_hvgs.csv
        else
            hvg_csv=outputs/kotliar_hvgs.csv
        fi
    fi

    echo "Patching and running incremental_pca fit..."
    ${params.python3_bin} \$(which render_config.py) \
        --patch pca_fit_config.yaml:${pca_fit_config} \
        "dataset_dir=\${_train_dataset_dir}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca fit -c pca_fit_config.yaml

    if [ "${predict_dataset_dir}" != "${fit_dataset_dir}" ]; then
        rm -r \${_train_dataset_dir}
        _predict_dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${predict_dataset_dir}" "${params.smoke_test}")
    else
        _predict_dataset_dir=\${_train_dataset_dir}
    fi

    echo "Patching and running incremental_pca predict..."
    ${params.python3_bin} \$(which render_config.py) \
        --patch pca_predict_config.yaml:${pca_predict_config} \
        "dataset_dir=\${_predict_dataset_dir}"

    run_with_gpu_monitor.sh cellarium-ml incremental_pca predict -c pca_predict_config.yaml
    """
}
