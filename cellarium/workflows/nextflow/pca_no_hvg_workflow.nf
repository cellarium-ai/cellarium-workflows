#!/usr/bin/env nextflow

// Train PCA on one dataset, run prediction on a (potentially different) dataset.
// ONEPASS and HVG come from some previous run and are not re-run here.
// INCREMENTAL_PCA trains on train_dataset_dir, then INCREMENTAL_PCA_PREDICT runs
// on predict_dataset_dir on a separate machine — avoiding co-localising both datasets.

params.train_dataset_dir  = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.predict_dataset_dir = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_vsindex_10x/extract_files'
params.outdir             = 'gs://cellarium-dev-central/workflows/nextflow_cas_pca'
params.config_pca         = "${projectDir}/../configs/incremental_pca.yaml.j2"
params.config_pca_predict = "${projectDir}/../configs/incremental_pca_predict.yaml.j2"
params.onepass_csv           = 'gs://cellarium-dev-central/workflows/nextflow_cas_pca/onepass_mean_var_std/outputs/onepass.csv'  // from ONEPASS step
params.hvg_csv               = 'gs://cellarium-dev-central/workflows/nextflow_cas_pca/onepass_mean_var_std/seurat_hvg.csv'  // from HVG step
params.n_components       = 32
params.n_top_genes        = 4000
params.batch_index_n      = 'null'
params.num_workers        = 8
params.prefetch_factor    = 4
params.var_names_key      = 'feature_id'
params.accelerator        = 'auto'
params.batch_size         = 5000
params.max_cache_size     = 4
params.use_pflogpf        = false  // whether to use PFlogPF data normalization
params.zscore_genes       = true  // whether to z-score genes before PCA
params.total_mrna_umis_key = 'raw_sum'
params.apply_normalize_total = true
params.target_count      = 10000
params.apply_log1p     = true
params.sparse_dataloader = true

include { INCREMENTAL_PCA_PLUS_PREDICTION} from './modules/pca_plus_predict.nf'

workflow {
    train_ch       = Channel.value(
        params.train_dataset_dir.startsWith('gs://')
            ? params.train_dataset_dir
            : file(params.train_dataset_dir).toAbsolutePath().toString())
    predict_ch     = Channel.value(
        params.predict_dataset_dir.startsWith('gs://')
            ? params.predict_dataset_dir
            : file(params.predict_dataset_dir).toAbsolutePath().toString())
    onepass_csv_ch     = Channel.value(file(params.onepass_csv))
    hvg_csv_ch         = Channel.value(file(params.hvg_csv))
    cfg_pca_ch         = Channel.value(file(params.config_pca))
    cfg_pca_predict_ch = Channel.value(file(params.config_pca_predict))

    // INCREMENTAL_PCA_PLUS_PREDICTION waits for both, runs prediction on same machine
    pca_out = INCREMENTAL_PCA_PLUS_PREDICTION(
        fit_dataset_dir=train_ch,
        predict_dataset_dir=predict_ch,
        onepass_csv=onepass_csv_ch,
        hvg_csv=hvg_csv_ch,
        base_fit_yaml=cfg_pca_ch,
        base_predict_yaml=cfg_pca_predict_ch
    )
}
