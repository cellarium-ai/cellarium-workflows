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
params.batch_index_n      = 'null'
params.categorical_covariate_keys = 'null'  // for scVI, a comma-separated list of keys in the anndata obs
params.n_latent           = 128  // for scVI, the dimensionality of the latent space

def _run_ts = new java.text.SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date())
params.run_outdir = params.run_outdir ?: "${params.outdir}/${params.run_label}/${_run_ts}"

include { RENDER_SCVI_CONFIGS } from './modules/render_configs.nf'
include { SCVI } from './modules/scvi.nf'

workflow {
    dataset_ch = Channel.value(
        params.dataset_dir.startsWith('gs://')
            ? params.dataset_dir
            : file(params.dataset_dir).toAbsolutePath().toString())
    hvg_csv_ch     = Channel.value(file(params.hvg_csv))
    configs_dir_ch = Channel.value(file(params.config_scvi).parent)

    render_out = RENDER_SCVI_CONFIGS(
        dataset_dir  = dataset_ch,
        hvg_csv_path = params.hvg_csv,
        run_name     = workflow.runName,
        session_id   = workflow.sessionId,
        configs_dir  = configs_dir_ch
    )

    SCVI(
        dataset_dir = dataset_ch,
        hvg_csv     = hvg_csv_ch,
        scvi_config = render_out.scvi_config
    )
}
