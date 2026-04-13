#!/usr/bin/env python3
"""Infer shard_size and last_shard_size from a directory of .h5ad files.

Reads n_obs from the first and last file (lexicographic order) using h5py
so we don't pay the cost of loading full AnnData metadata.

Usage:
    infer_shards.py <directory>

Output (space-separated on one line):
    <shard_size> <last_shard_size>

last_shard_size is printed as 'null' when it equals shard_size (i.e. the last
shard is full) or when there is only one file, matching cellarium-ml's
convention that null means "same as shard_size".
"""
import sys
from pathlib import Path

import h5py


def n_obs(path: Path) -> int:
    with h5py.File(path, "r") as f:
        # Standard AnnData layout: obs group, index attribute points to the
        # obs index dataset whose length == n_obs.
        obs = f["obs"]
        index_key = obs.attrs.get("_index", obs.attrs.get("index", None))
        if index_key is not None:
            return f["obs"][index_key].shape[0]
        # Fallback: obs is a structured dataset (older AnnData)
        return obs.shape[0]


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <directory>", file=sys.stderr)
        sys.exit(1)

    directory = Path(sys.argv[1])
    files = sorted(directory.glob("*.h5ad"))

    if not files:
        print(f"No .h5ad files found in {directory}", file=sys.stderr)
        sys.exit(1)

    shard_size = n_obs(files[0])
    last_size = n_obs(files[-1])

    last_shard_size = "null" if (len(files) == 1 or last_size == shard_size) else str(last_size)

    print(f"{shard_size} {last_shard_size}")


if __name__ == "__main__":
    main()
