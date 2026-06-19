#!/usr/bin/env nextflow

params.dataset_dir        = 'gs://cellarium-nexus-file-system-3293a8/pipeline/data-extracts/20260403_cas_pca_model_10x/extract_files'
params.outdir             = 'gs://cellarium-dev-central/workflows/tmp'
params.config_scvi        = "${projectDir}/../configs/scvi.yaml.j2"
params.hvg_csv            = 'hvg.csv'  // from HVG step

params.num_workers        = 8
params.prefetch_factor    = 4
params.var_names_key      = 'null'
params.accelerator        = 'auto'
params.batch_size         = 5000
params.max_cache_size     = 4

params.batch_key          = 'assay_dataset_id_donor_id_suspension_type'
params.categorical_covariate_keys = 'null'  // for scVI, a comma- separated list of keys in the anndata obs that should be treated as categorical covariates
params.n_latent           = 128  // for scVI, the dimensionality of the latent space

include { SCVI } from './modules/scvi.nf'

workflow {
    dataset_ch = Channel.value(
        params.dataset_dir.startsWith('gs://')
            ? params.dataset_dir
            : file(params.dataset_dir).toAbsolutePath().toString())
    cfg_scvi_ch        = Channel.value(file(params.config_scvi))

    scvi_out = SCVI(
        dataset_ch,
        Channel.value(file(params.hvg_csv)),
        cfg_scvi_ch
    )
}
