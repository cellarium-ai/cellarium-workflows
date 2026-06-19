#!/usr/bin/env nextflow

params.fit_dataset_dir        = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.predict_dataset_dir    = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.outdir             = 'gs://cellarium-dev-central/workflows/tmp'
params.config_onepass     = "${projectDir}/../configs/onepass_mean_var_std.yaml.j2"
params.n_components       = 64
params.n_top_genes        = 8000
params.batch_index_n      = 'null'
params.num_workers        = 8
params.prefetch_factor    = 4
params.var_names_key      = 'null'
params.accelerator        = 'auto'
params.batch_size         = 5000
params.max_cache_size     = 4
params.hvg_method         = 'seurat'  // or 'kotliar' or 'seurat_v3'
params.seurat_v3_flavor   = 'seurat_v3'  // or 'seurat_v3_paper' -- only relevant if hvg_method is seurat_v3
params.use_pflogpf        = false  // whether to use PFlogPF data normalization
params.zscore_genes       = true  // whether to z-score genes before PCA
params.total_mrna_umis_key = 'raw_sum'
params.apply_normalize_total = true
params.target_count      = 10000
params.apply_log1p     = true
params.sparse_dataloader = true

// Compute a timestamped output root so successive runs don't overwrite each other.
// Override with --run_outdir gs://... to write to a specific path.
def _run_ts = new java.text.SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date())
params.run_outdir = params.run_outdir ?: "${params.outdir}/${params.run_label}/${_run_ts}"

def VALID_HVG_METHODS = ['seurat_v3', 'seurat', 'kotliar']
if (!(params.hvg_method in VALID_HVG_METHODS)) {
    error "Invalid hvg_method '${params.hvg_method}'. Must be one of: ${VALID_HVG_METHODS.join(', ')}"
}

include { RENDER_PCA_CONFIGS } from './modules/render_configs.nf'
include { ONEPASS_HVG_INCREMENTAL_PCA_PLUS_PREDICTION } from './modules/combo_hvg_pca_predict.nf'

workflow {
    fit_dataset_ch = Channel.value(
        params.fit_dataset_dir.startsWith('gs://')
            ? params.fit_dataset_dir
            : file(params.fit_dataset_dir).toAbsolutePath().toString())
    predict_dataset_ch = Channel.value(
        params.predict_dataset_dir.startsWith('gs://')
            ? params.predict_dataset_dir
            : file(params.predict_dataset_dir).toAbsolutePath().toString())

    // configs_dir stages the entire configs/ directory into each process work dir,
    // making all templates and partials available to render_config.py.
    configs_dir_ch = Channel.value(file(params.config_onepass).parent)

    // Run locally first: render preview configs + write provenance record to GCS.
    render_out = RENDER_PCA_CONFIGS(
        fit_dataset_dir    = fit_dataset_ch,
        predict_dataset_dir = predict_dataset_ch,
        hvg_method         = params.hvg_method,
        run_name           = workflow.runName,
        session_id         = workflow.sessionId,
        configs_dir        = configs_dir_ch
    )

    // Dispatch the full pipeline to a single GCP GPU VM.
    ONEPASS_HVG_INCREMENTAL_PCA_PLUS_PREDICTION(
        fit_dataset_dir      = fit_dataset_ch,
        predict_dataset_dir  = predict_dataset_ch,
        hvg_method           = params.hvg_method,
        onepass_config       = render_out.onepass_config,
        pca_fit_config       = render_out.pca_fit_config,
        pca_predict_config   = render_out.pca_predict_config,
        seurat_v3_hvg_config = render_out.seurat_v3_hvg_config
    )
}
