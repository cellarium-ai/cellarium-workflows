#!/usr/bin/env python3
"""Write run provenance metadata as a JSON file.

Usage:
    write_metadata.py [--output run_metadata.json] [--params-file context.json] KEY=VALUE ...

All KEY=VALUE pairs are stored as top-level string fields in the JSON.
If --params-file is given, its contents are embedded under the "params" key.

Nextflow places this script on $PATH for every task when it lives in nextflow/bin/.
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "fields", nargs="*", metavar="key=value",
        help="Metadata fields to record (stored as strings)",
    )
    parser.add_argument(
        "--output", default="run_metadata.json",
        help="Output JSON path (default: run_metadata.json)",
    )
    parser.add_argument(
        "--params-file", metavar="FILE",
        help="JSON file whose contents are embedded under the 'params' key",
    )
    args = parser.parse_args()

    metadata: dict = {}

    for item in args.fields:
        key, _, value = item.partition("=")
        if key:
            metadata[key] = value  # keep as strings for provenance clarity

    if args.params_file:
        with open(args.params_file) as fh:
            metadata["params"] = json.load(fh)

    Path(args.output).write_text(json.dumps(metadata, indent=2))
    print(f"Metadata written to {args.output}")


if __name__ == "__main__":
    main()
