#!/usr/bin/env nextflow

params.dataset_dir        = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.outdir             = 'gs://cellarium-dev-central/workflows/tmp'
params.config_onepass     = "${projectDir}/../configs/onepass_mean_var_std.yaml.j2"
params.config_hvg         = "${projectDir}/../configs/hvg_seurat_v3.yaml.j2"
params.config_pca         = "${projectDir}/../configs/incremental_pca.yaml.j2"
params.config_pca_predict = "${projectDir}/../configs/incremental_pca_predict.yaml.j2"
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
params.use_pflogpf        = false  // whether to use PFlogPF data normalization
params.zscore_genes       = true  // whether to z-score genes before PCA
params.total_mrna_umis_key = 'raw_sum'
params.apply_normalize_total = true
params.target_count      = 10000
params.apply_log1p     = true
params.sparse_dataloader = true

include { ONEPASS_MEAN_VAR_WITH_HVGS } from './modules/onepass_with_hvgs.nf'
include { SEURAT_V3_HIGHLY_VARIABLE_GENES   } from './modules/seurat_v3_hvg.nf'
include { INCREMENTAL_PCA_PLUS_PREDICTION } from './modules/pca_plus_predict.nf'

workflow {
    dataset_ch = Channel.value(
        params.dataset_dir.startsWith('gs://')
            ? params.dataset_dir
            : file(params.dataset_dir).toAbsolutePath().toString())
    cfg_onepass_ch     = Channel.value(file(params.config_onepass))
    cfg_hvg_ch         = Channel.value(file(params.config_hvg))
    cfg_pca_ch         = Channel.value(file(params.config_pca))
    cfg_pca_predict_ch = Channel.value(file(params.config_pca_predict))

    // ONEPASS plus HVG helper scripts
    onepass_out = ONEPASS_MEAN_VAR_WITH_HVGS(
        dataset_dir=dataset_ch, 
        base_yaml=cfg_onepass_ch, 
        n_top_genes=params.n_top_genes
    )

    // seurat_v3 HVG optionally (in parallel)
    if (params.hvg_method == 'seurat_v3') {
        hvg_out = SEURAT_V3_HIGHLY_VARIABLE_GENES(dataset_ch, cfg_hvg_ch)
        hvg_csv = hvg_out.hvg_csv
    } else {
        hvg_csv = params.hvg_method == 'seurat' ? onepass_out.seurat_hvg_csv : onepass_out.kotliar_hvg_csv
    }

    // INCREMENTAL_PCA_PLUS_PREDICTION waits for both, runs prediction on same machine
    pca_out = INCREMENTAL_PCA_PLUS_PREDICTION(
        dataset_dir=dataset_ch,
        onepass_csv=onepass_out.onepass_csv,
        hvg_csv=hvg_csv,
        base_yaml=cfg_pca_ch,
        base_predict_yaml=cfg_pca_predict_ch
    )
}
