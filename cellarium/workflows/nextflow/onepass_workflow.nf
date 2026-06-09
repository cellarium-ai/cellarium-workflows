#!/usr/bin/env nextflow

params.dataset_dir    = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.outdir         = 'gs://cellarium-dev-central/workflows/tmp'
params.config_onepass = "${projectDir}/../configs/onepass_mean_var_std.yaml.j2"
params.num_workers     = 8
params.prefetch_factor = 4
params.var_names_key   = 'null'
params.total_mrna_umis_key = 'null'
params.apply_normalize_total = true
params.target_count      = 10000
params.apply_log1p     = true
params.sparse_dataloader = true
params.accelerator     = 'auto'
params.batch_size      = 5000
params.max_cache_size  = 4

include { ONEPASS_MEAN_VAR } from './modules/onepass.nf'

workflow {
    dataset_ch = Channel.value(
        params.dataset_dir.startsWith('gs://')
            ? params.dataset_dir
            : file(params.dataset_dir).toAbsolutePath().toString())
    cfg_ch     = Channel.value(file(params.config_onepass))

    ONEPASS_MEAN_VAR(dataset_ch, cfg_ch)
}