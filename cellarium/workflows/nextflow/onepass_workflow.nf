#!/usr/bin/env nextflow

params.dataset_dir    = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.outdir         = 'gs://cellarium-dev-central/workflows/tmp'
params.config_onepass = "${projectDir}/../configs/onepass_mean_var_std.yaml.j2"

include { ONEPASS_MEAN_VAR } from './modules/onepass.nf'

workflow {
    dataset_ch = Channel.value(file(params.dataset_dir))
    cfg_ch     = Channel.value(file(params.config_onepass))

    ONEPASS_MEAN_VAR(dataset_ch, cfg_ch)
}