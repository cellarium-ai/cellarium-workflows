#!/usr/bin/env nextflow

// Train PCA on one dataset, run prediction on a (potentially different) dataset.
// ONEPASS and HVG use the training dataset.
// INCREMENTAL_PCA trains on train_dataset_dir, then INCREMENTAL_PCA_PREDICT runs
// on predict_dataset_dir on a separate machine — avoiding co-localising both datasets.

params.train_dataset_dir  = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.predict_dataset_dir = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_vsindex_10x/extract_files'
params.outdir             = 'gs://cellarium-dev-central/workflows/nextflow_cas_pca'
params.config_onepass     = "${projectDir}/../configs/onepass_mean_var_std.yaml.j2"
params.config_hvg         = "${projectDir}/../configs/hvg_seurat_v3.yaml.j2"
params.config_pca         = "${projectDir}/../configs/incremental_pca.yaml.j2"
params.config_pca_predict = "${projectDir}/../configs/incremental_pca_predict.yaml.j2"
params.n_components       = 64
params.n_top_genes        = 4000
params.flavor             = 'seurat_v3'
params.batch_index_n      = 'null'
params.num_workers        = 8
params.prefetch_factor    = 4
params.var_names_key      = 'feature_id'
params.accelerator        = 'auto'
params.batch_size         = 5000

include { ONEPASS_MEAN_VAR        } from './modules/onepass.nf'
include { HIGHLY_VARIABLE_GENES   } from './modules/hvg.nf'
include { INCREMENTAL_PCA         } from './modules/pca.nf'
include { INCREMENTAL_PCA_PREDICT } from './modules/pca_predict.nf'

workflow {
    train_ch       = Channel.value(
        params.train_dataset_dir.startsWith('gs://')
            ? params.train_dataset_dir
            : file(params.train_dataset_dir).toAbsolutePath().toString())
    predict_ch     = Channel.value(
        params.predict_dataset_dir.startsWith('gs://')
            ? params.predict_dataset_dir
            : file(params.predict_dataset_dir).toAbsolutePath().toString())
    cfg_onepass_ch     = Channel.value(file(params.config_onepass))
    cfg_hvg_ch         = Channel.value(file(params.config_hvg))
    cfg_pca_ch         = Channel.value(file(params.config_pca))
    cfg_pca_predict_ch = Channel.value(file(params.config_pca_predict))

    // ONEPASS and HVG run in parallel on the training dataset
    onepass_out = ONEPASS_MEAN_VAR(train_ch, cfg_onepass_ch)
    hvg_out     = HIGHLY_VARIABLE_GENES(train_ch, cfg_hvg_ch)

    // INCREMENTAL_PCA trains on the training dataset
    pca_out = INCREMENTAL_PCA(
        train_ch,
        onepass_out.onepass_csv,
        hvg_out.hvg_csv,
        cfg_pca_ch
    )

    // INCREMENTAL_PCA_PREDICT runs on the prediction dataset (separate machine)
    INCREMENTAL_PCA_PREDICT(
        predict_ch,
        pca_out.final_model,
        onepass_out.onepass_csv,
        hvg_out.hvg_csv,
        cfg_pca_predict_ch
    )
}
