"""Cellarium CLI execution code for kubeflow components."""
from cellarium.ml.cli import main as cellarium_ml_cli

cellarium_ml_cli(args=[tool, subcommand, "--config", config])
