#!/usr/bin/env nextflow

// params.dataset_dir = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.dataset_dir = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/czi_human_primary_gr300genes_fullschema/extract_files'
params.outdir      = 'gs://cellarium-dev-central/workflows/czi_human_primary_gr300genes_fullschema_hvg_4000'
params.config_hvg    = "${projectDir}/../configs/hvg_seurat_v3.yaml.j2"
params.n_top_genes   = 4000
params.flavor        = 'seurat_v3'
params.batch_index_n = 'assay_suspension_type'
params.num_workers     = 8
params.prefetch_factor = 4
params.var_names_key   = 'null'
params.accelerator     = 'auto'
params.batch_size      = 5000
params.max_cache_size  = 4

include { SEURAT_V3_HIGHLY_VARIABLE_GENES } from './modules/seurat_v3_hvg.nf'

workflow {
    dataset_ch = Channel.value(
        params.dataset_dir.startsWith('gs://')
            ? params.dataset_dir
            : file(params.dataset_dir).toAbsolutePath().toString())
    cfg_ch     = Channel.value(file(params.config_hvg))

    SEURAT_V3_HIGHLY_VARIABLE_GENES(dataset_ch, cfg_ch)
}
