/*
 * render_configs.nf
 *
 * Local pre-render processes – one per workflow type.
 *
 * These processes run on the SUBMITTING machine (executor = 'local') before
 * any remote GPU job is dispatched.  They produce:
 *
 *   run_context.json   – coerced params, shared by all downstream GCP processes
 *                        as a --context-file argument to render_config.py.
 *   run_metadata.json  – human-readable provenance record: dataset paths,
 *                        timestamps, git SHA, Nextflow run name/session, full
 *                        params dump.
 *   preview_*.yaml     – fully rendered configs with filenames: [] / limits: []
 *                        (placeholder – dataset not yet scanned).  Archived to
 *                        params.run_outdir/configs/ so you have a pre-run record.
 *
 * All processes are overridden to executor = 'local' in nextflow.config via:
 *   process { withName: ~/RENDER_.*_CONFIGS/ { executor = 'local' } }
 */


// ── PCA workflow (all-in-one combo: onepass + HVG + PCA fit + PCA predict) ──

process RENDER_PCA_CONFIGS {
    publishDir "${params.run_outdir}/configs/", mode: 'copy'

    input:
    val  fit_dataset_dir
    val  predict_dataset_dir
    val  hvg_method
    val  run_name
    val  session_id
    path configs_dir

    output:
    path 'run_context.json',              emit: context
    path 'run_metadata.json',             emit: metadata
    path 'onepass_config.yaml',           emit: onepass_config
    path 'pca_fit_config.yaml',           emit: pca_fit_config
    path 'pca_predict_config.yaml',       emit: pca_predict_config
    path 'seurat_v3_hvg_config.yaml',     emit: seurat_v3_hvg_config

    script:
    """
    # ── Compute hvg_csv path from hvg_method (pre-bake into context) ──
    if [ "${hvg_method}" = "seurat_v3" ]; then
        _hvg_csv="outputs/hvg_genes__top${params.n_top_genes}__hvg_only.csv"
    elif [ "${hvg_method}" = "seurat" ]; then
        _hvg_csv="outputs/seurat_hvgs.csv"
    else
        _hvg_csv="outputs/kotliar_hvgs.csv"
    fi

    # ── Dump shared context (all model/transform params + fixed inter-step paths) ──
    ${params.python3_bin} \$(which render_config.py) \
        --dump-context run_context.json \
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
        "max_cache_size=${params.max_cache_size}" \
        "zscore_genes=${params.zscore_genes}" \
        "n_components=${params.n_components}" \
        "n_top_genes=${params.n_top_genes}" \
        "batch_index_n=${params.batch_index_n}" \
        "seurat_v3_flavor=${params.seurat_v3_flavor}" \
        "cellarium_ml_ref=${params.cellarium_ml_ref}" \
        "onepass_csv=outputs/onepass_mean_var_std.csv" \
        "pca_model=outputs/checkpoints/last.ckpt" \
        "hvg_csv=\${_hvg_csv}"

    # ── Render runtime configs (filenames/limits default to [] — patched on VM) ──
    ${params.python3_bin} \$(which render_config.py) \
        --context-file run_context.json \
        --template onepass_config.yaml:${configs_dir}/onepass_mean_var_std.yaml.j2 \
        --template pca_fit_config.yaml:${configs_dir}/incremental_pca.yaml.j2 \
        --template pca_predict_config.yaml:${configs_dir}/incremental_pca_predict.yaml.j2 \
        --template seurat_v3_hvg_config.yaml:${configs_dir}/hvg_seurat_v3.yaml.j2

    # ── Write provenance metadata ──
    _git_sha=\$(git -C "${projectDir}" rev-parse HEAD 2>/dev/null || echo unknown)
    ${params.python3_bin} \$(which write_metadata.py) \
        --output run_metadata.json \
        --params-file run_context.json \
        "fit_dataset_dir=${fit_dataset_dir}" \
        "predict_dataset_dir=${predict_dataset_dir}" \
        "hvg_method=${hvg_method}" \
        "timestamp=\$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "cellarium_ml_ref=${params.cellarium_ml_ref}" \
        "nextflow_run_name=${run_name}" \
        "nextflow_session_id=${session_id}" \
        "workflows_git_sha=\${_git_sha}"
    """
}


// ── Onepass-only workflow ──────────────────────────────────────────────────

process RENDER_ONEPASS_CONFIGS {
    publishDir "${params.run_outdir}/configs/", mode: 'copy'

    input:
    val  dataset_dir
    val  run_name
    val  session_id
    path configs_dir

    output:
    path 'run_context.json',     emit: context
    path 'run_metadata.json',    emit: metadata
    path 'onepass_config.yaml',  emit: onepass_config

    script:
    """
    ${params.python3_bin} \$(which render_config.py) \
        --dump-context run_context.json \
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
        "max_cache_size=${params.max_cache_size}" \
        "cellarium_ml_ref=${params.cellarium_ml_ref}"

    ${params.python3_bin} \$(which render_config.py) \
        --context-file run_context.json \
        --template onepass_config.yaml:${configs_dir}/onepass_mean_var_std.yaml.j2

    _git_sha=\$(git -C "${projectDir}" rev-parse HEAD 2>/dev/null || echo unknown)
    ${params.python3_bin} \$(which write_metadata.py) \
        --output run_metadata.json \
        --params-file run_context.json \
        "dataset_dir=${dataset_dir}" \
        "timestamp=\$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "cellarium_ml_ref=${params.cellarium_ml_ref}" \
        "nextflow_run_name=${run_name}" \
        "nextflow_session_id=${session_id}" \
        "workflows_git_sha=\${_git_sha}"
    """
}


// ── Seurat-v3 HVG-only workflow ───────────────────────────────────────────

process RENDER_SEURAT_HVG_CONFIGS {
    publishDir "${params.run_outdir}/configs/", mode: 'copy'

    input:
    val  dataset_dir
    val  run_name
    val  session_id
    path configs_dir

    output:
    path 'run_context.json',           emit: context
    path 'run_metadata.json',          emit: metadata
    path 'seurat_v3_hvg_config.yaml',  emit: seurat_v3_hvg_config

    script:
    """
    ${params.python3_bin} \$(which render_config.py) \
        --dump-context run_context.json \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "var_names_key=${params.var_names_key}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "max_cache_size=${params.max_cache_size}" \
        "n_top_genes=${params.n_top_genes}" \
        "flavor=${params.seurat_v3_flavor}" \
        "batch_index_n=${params.batch_index_n}" \
        "cellarium_ml_ref=${params.cellarium_ml_ref}"

    ${params.python3_bin} \$(which render_config.py) \
        --context-file run_context.json \
        --template seurat_v3_hvg_config.yaml:${configs_dir}/hvg_seurat_v3.yaml.j2

    _git_sha=\$(git -C "${projectDir}" rev-parse HEAD 2>/dev/null || echo unknown)
    ${params.python3_bin} \$(which write_metadata.py) \
        --output run_metadata.json \
        --params-file run_context.json \
        "dataset_dir=${dataset_dir}" \
        "timestamp=\$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "cellarium_ml_ref=${params.cellarium_ml_ref}" \
        "nextflow_run_name=${run_name}" \
        "nextflow_session_id=${session_id}" \
        "workflows_git_sha=\${_git_sha}"
    """
}


// ── scVI workflow ──────────────────────────────────────────────────────────

process RENDER_SCVI_CONFIGS {
    publishDir "${params.run_outdir}/configs/", mode: 'copy'

    input:
    val  dataset_dir
    val  hvg_csv_path
    val  run_name
    val  session_id
    path configs_dir

    output:
    path 'run_context.json',   emit: context
    path 'run_metadata.json',  emit: metadata
    path 'scvi_config.yaml',   emit: scvi_config

    script:
    """
    ${params.python3_bin} \$(which render_config.py) \
        --dump-context run_context.json \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "var_names_key=${params.var_names_key}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "max_cache_size=${params.max_cache_size}" \
        "batch_key=${params.batch_key}" \
        "categorical_covariate_keys=${params.categorical_covariate_keys}" \
        "n_latent=${params.n_latent}" \
        "batch_index_n=${params.batch_index_n}" \
        "hvg_csv=${hvg_csv_path}" \
        "cellarium_ml_ref=${params.cellarium_ml_ref}"

    ${params.python3_bin} \$(which render_config.py) \
        --context-file run_context.json \
        --template scvi_config.yaml:${configs_dir}/scvi.yaml.j2

    _git_sha=\$(git -C "${projectDir}" rev-parse HEAD 2>/dev/null || echo unknown)
    ${params.python3_bin} \$(which write_metadata.py) \
        --output run_metadata.json \
        --params-file run_context.json \
        "dataset_dir=${dataset_dir}" \
        "hvg_csv=${hvg_csv_path}" \
        "timestamp=\$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "cellarium_ml_ref=${params.cellarium_ml_ref}" \
        "nextflow_run_name=${run_name}" \
        "nextflow_session_id=${session_id}" \
        "workflows_git_sha=\${_git_sha}"
    """
}


// ── PCA-no-HVG workflow (pre-existing onepass_csv and hvg_csv) ────────────

process RENDER_PCA_NO_HVG_CONFIGS {
    publishDir "${params.run_outdir}/configs/", mode: 'copy'

    input:
    val  train_dataset_dir
    val  predict_dataset_dir
    val  onepass_csv_path
    val  hvg_csv_path
    val  run_name
    val  session_id
    path configs_dir

    output:
    path 'run_context.json',         emit: context
    path 'run_metadata.json',        emit: metadata
    path 'pca_fit_config.yaml',      emit: pca_fit_config
    path 'pca_predict_config.yaml',  emit: pca_predict_config

    script:
    """
    ${params.python3_bin} \$(which render_config.py) \
        --dump-context run_context.json \
        "num_workers=${params.num_workers}" \
        "prefetch_factor=${params.prefetch_factor}" \
        "var_names_key=${params.var_names_key}" \
        "accelerator=${params.accelerator}" \
        "batch_size=${params.batch_size}" \
        "max_cache_size=${params.max_cache_size}" \
        "use_pflogpf=${params.use_pflogpf}" \
        "apply_normalize_total=${params.apply_normalize_total}" \
        "target_count=${params.target_count}" \
        "apply_log1p=${params.apply_log1p}" \
        "zscore_genes=${params.zscore_genes}" \
        "n_components=${params.n_components}" \
        "onepass_csv=${onepass_csv_path}" \
        "hvg_csv=${hvg_csv_path}" \
        "pca_model=outputs/checkpoints/last.ckpt" \
        "cellarium_ml_ref=${params.cellarium_ml_ref}"

    ${params.python3_bin} \$(which render_config.py) \
        --context-file run_context.json \
        --template pca_fit_config.yaml:${configs_dir}/incremental_pca.yaml.j2 \
        --template pca_predict_config.yaml:${configs_dir}/incremental_pca_predict.yaml.j2

    _git_sha=\$(git -C "${projectDir}" rev-parse HEAD 2>/dev/null || echo unknown)
    ${params.python3_bin} \$(which write_metadata.py) \
        --output run_metadata.json \
        --params-file run_context.json \
        "train_dataset_dir=${train_dataset_dir}" \
        "predict_dataset_dir=${predict_dataset_dir}" \
        "onepass_csv=${onepass_csv_path}" \
        "hvg_csv=${hvg_csv_path}" \
        "timestamp=\$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "cellarium_ml_ref=${params.cellarium_ml_ref}" \
        "nextflow_run_name=${run_name}" \
        "nextflow_session_id=${session_id}" \
        "workflows_git_sha=\${_git_sha}"
    """
}
