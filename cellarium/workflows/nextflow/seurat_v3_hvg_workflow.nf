#!/usr/bin/env nextflow

// params.dataset_dir = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.dataset_dir = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/czi_human_primary_gr300genes_fullschema/extract_files'
params.outdir      = 'gs://cellarium-dev-central/workflows/czi_human_primary_gr300genes_fullschema_hvg_4000'
params.config_hvg    = "${projectDir}/../configs/hvg_seurat_v3.yaml.j2"
params.n_top_genes   = 4000
params.seurat_v3_flavor        = 'seurat_v3'
params.batch_index_n = 'assay_suspension_type'
params.num_workers     = 8
params.prefetch_factor = 4
params.var_names_key   = 'null'
params.accelerator     = 'auto'
params.batch_size      = 5000
params.max_cache_size  = 4

def _run_ts = new java.text.SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date())
params.run_outdir = params.run_outdir ?: "${params.outdir}/${params.run_label}/${_run_ts}"

include { RENDER_SEURAT_HVG_CONFIGS } from './modules/render_configs.nf'
include { SEURAT_V3_HIGHLY_VARIABLE_GENES } from './modules/seurat_v3_hvg.nf'

workflow {
    dataset_ch = Channel.value(
        params.dataset_dir.startsWith('gs://')
            ? params.dataset_dir
            : file(params.dataset_dir).toAbsolutePath().toString())
    configs_dir_ch = Channel.value(file(params.config_hvg).parent)

    render_out = RENDER_SEURAT_HVG_CONFIGS(
        dataset_dir = dataset_ch,
        run_name    = workflow.runName,
        session_id  = workflow.sessionId,
        configs_dir = configs_dir_ch
    )

    SEURAT_V3_HIGHLY_VARIABLE_GENES(
        dataset_dir          = dataset_ch,
        seurat_v3_hvg_config = render_out.seurat_v3_hvg_config
    )
}
