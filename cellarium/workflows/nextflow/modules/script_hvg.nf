process HIGHLY_VARIABLE_GENES {
    publishDir "${params.outdir}/hvg/", mode: 'copy'

    input:
    val  onepass_csv
    val  method
    val  n_top_genes

    output:
    path 'hvgs.csv', emit: hvg_csv

    script:
    """
    mkdir -p outputs

    maybe_pip_install.sh "${params.cellarium_ml_ref}"
    _dataset_dir=\$(stage_dataset.sh "${params.gcp_download}" "${dataset_dir}")

    ${params.python3_bin} \$(which hvg_helper.py) ${method} ${n_top_genes} ${onepass_csv} --output hvgs.csv
    """
}
