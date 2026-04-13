#!/usr/bin/env python3
"""Render a Jinja2 YAML template with key=value parameters.

Usage:
    render_config.py <template.yaml.j2> key=value [key=value ...] [--output run_config.yaml]

Values are automatically coerced:
    "None" or "null"  -> None  (falsy; omits conditional blocks)
    "true" / "false"  -> bool
    digits-only       -> int
    "" (empty)        -> ""    (also falsy; same effect as None for {% if %} checks)
    anything else     -> str

Special key:
    dataset_dir=<path>  Scans the directory for *.h5ad files (lexicographic order),
                        reads n_obs from each via h5py, and injects two context vars:
                          filenames  - list of absolute file path strings
                          limits     - cumulative sum of n_obs across files

Nextflow places this script on $PATH for every task when it lives in nextflow/bin/.
"""
import argparse
import sys
from pathlib import Path


def coerce(value: str):
    """Convert a CLI string value to an appropriate Python type."""
    if value in ("None", "null"):
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


def n_obs(path: Path) -> int:
    import h5py
    with h5py.File(path, "r") as f:
        obs = f["obs"]
        index_key = obs.attrs.get("_index", obs.attrs.get("index", None))
        if index_key is not None:
            return f["obs"][index_key].shape[0]
        return obs.shape[0]


def dataset_dir_to_filenames_and_limits(dataset_dir: str):
    files = sorted(Path(dataset_dir).glob("*.h5ad"))
    if not files:
        print(f"Error: no .h5ad files found in {dataset_dir}", file=sys.stderr)
        sys.exit(1)
    counts = [n_obs(f) for f in files]
    filenames = [str(f) for f in files]
    limits = []
    cumsum = 0
    for c in counts:
        cumsum += c
        limits.append(cumsum)
    return filenames, limits


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("template", help="Path to .yaml.j2 template file")
    parser.add_argument("variables", nargs="*", metavar="key=value", help="Template variables")
    parser.add_argument("--output", default="run_config.yaml", help="Output path (default: run_config.yaml)")
    args = parser.parse_args()

    try:
        from jinja2 import Environment, FileSystemLoader, StrictUndefined
    except ImportError:
        print("Error: jinja2 is not installed. Run: pip install jinja2", file=sys.stderr)
        sys.exit(1)

    template_path = Path(args.template)
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_path.name)

    context = {}
    for item in args.variables:
        key, _, value = item.partition("=")
        if key:
            context[key] = coerce(value)

    if "dataset_dir" in context:
        dataset_dir = context.pop("dataset_dir")
        context["filenames"], context["limits"] = dataset_dir_to_filenames_and_limits(dataset_dir)

    rendered = template.render(**context)
    Path(args.output).write_text(rendered)


if __name__ == "__main__":
    main()
