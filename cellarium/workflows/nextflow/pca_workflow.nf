#!/usr/bin/env nextflow

params.dataset_dir        = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.outdir             = 'gs://cellarium-dev-central/workflows/tmp'
params.config_onepass     = "${projectDir}/../configs/onepass_mean_var_std.yaml.j2"
params.config_hvg         = "${projectDir}/../configs/hvg_seurat_v3.yaml.j2"
params.config_pca         = "${projectDir}/../configs/incremental_pca.yaml.j2"
params.config_pca_predict = "${projectDir}/../configs/incremental_pca_predict.yaml.j2"
params.n_components       = 64
params.n_top_genes        = 8000
params.flavor             = 'seurat_v3'
params.batch_index_n      = 'null'
params.shard_size         = 10000
params.last_shard_size    = 'null'
params.num_workers        = 8
params.prefetch_factor    = 4
params.var_names_key      = 'null'
params.accelerator        = 'auto'
params.batch_size         = 5000

include { ONEPASS_MEAN_VAR        } from './modules/onepass.nf'
include { HIGHLY_VARIABLE_GENES   } from './modules/hvg.nf'
include { INCREMENTAL_PCA         } from './modules/pca.nf'
include { INCREMENTAL_PCA_PREDICT } from './modules/pca_predict.nf'

workflow {
    dataset_ch         = Channel.value(file(params.dataset_dir))
    cfg_onepass_ch     = Channel.value(file(params.config_onepass))
    cfg_hvg_ch         = Channel.value(file(params.config_hvg))
    cfg_pca_ch         = Channel.value(file(params.config_pca))
    cfg_pca_predict_ch = Channel.value(file(params.config_pca_predict))

    // ONEPASS and HVG run in parallel
    onepass_out = ONEPASS_MEAN_VAR(dataset_ch, cfg_onepass_ch)
    hvg_out     = HIGHLY_VARIABLE_GENES(dataset_ch, cfg_hvg_ch)

    // INCREMENTAL_PCA waits for both
    pca_out = INCREMENTAL_PCA(
        dataset_ch,
        onepass_out.onepass_csv,
        hvg_out.hvg_csv,
        cfg_pca_ch
    )

    // INCREMENTAL_PCA_PREDICT waits for the PCA model
    INCREMENTAL_PCA_PREDICT(
        dataset_ch,
        pca_out.final_model,
        onepass_out.onepass_csv,
        hvg_out.hvg_csv,
        cfg_pca_predict_ch
    )
}
