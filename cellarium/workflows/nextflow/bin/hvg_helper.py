#!/usr/bin/env python3
"""Run highly variable gene selection on a dataset directory and output a CSV file."""
import argparse
from pathlib import Path

import pandas as pd
import torch

from cellarium.ml.preprocessing import (
    kotliar_compute_highly_variable_genes,
    seurat_compute_highly_variable_genes,
)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("method", help="Method for HVG selection in ['seurat', 'kotliar']")
    parser.add_argument("n_top_genes", type=int, help="Number of top HVGs to select")
    parser.add_argument("onepass_csv", type=str, help="Path to one-pass CSV file")
    parser.add_argument("--output", default="hvgs.csv", help="Output path (default: hvgs.csv)")
    args = parser.parse_args()

    if args.method == "seurat":
        hvg_fun = seurat_compute_highly_variable_genes
    elif args.method == "kotliar":
        hvg_fun = kotliar_compute_highly_variable_genes
    else:
        raise ValueError(f"Error: Invalid method '{args.method}'. Must be 'seurat' or 'kotliar'.")
    
    onepass_df = pd.read_csv(args.onepass_csv)

    kwargs = {
        "var_names_g": onepass_df["var_names_g"].values,
        "mean_g": torch.from_numpy(onepass_df["mean_g"].values),
        "var_g": torch.from_numpy(onepass_df["var_g"].values),
        "n_top_genes": args.n_top_genes,
    }

    hvg_df = hvg_fun(**kwargs)
    hvg_df.to_csv(args.output, index=False)
    print(f"Highly variable genes written to {args.output}")


if __name__ == "__main__":
    main()
