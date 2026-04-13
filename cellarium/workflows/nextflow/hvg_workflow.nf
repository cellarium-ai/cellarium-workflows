#!/usr/bin/env nextflow

params.dataset_dir = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.outdir      = 'gs://cellarium-dev-central/workflows/tmp'
params.config_hvg    = "${projectDir}/../configs/hvg_seurat_v3.yaml.j2"
params.n_top_genes   = 8000
params.flavor        = 'seurat_v3'
params.batch_index_n = 'assay_suspension_type'

include { HIGHLY_VARIABLE_GENES } from './modules/hvg.nf'

workflow {
    dataset_ch = Channel.value(file(params.dataset_dir))
    cfg_ch     = Channel.value(file(params.config_hvg))

    HIGHLY_VARIABLE_GENES(dataset_ch, cfg_ch)
}
