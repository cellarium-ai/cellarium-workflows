process ONEPASS_MEAN_VAR {
    publishDir "${params.outdir}/onepass_mean_var_std/", mode: 'copy'

    input:
    path local_dataset
    path base_yaml

    output:
    path 'outputs/checkpoints/onepass_mean_var_std.ckpt', emit: checkpoint

    script:
    """
    mkdir -p outputs/checkpoints

    render_config.py ${base_yaml} \
        "dataset_glob=./${local_dataset}/*.h5ad"

    cellarium-ml onepass_mean_var fit -c run_config.yaml
    """
}
