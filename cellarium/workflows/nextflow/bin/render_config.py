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

    rendered = template.render(**context)
    Path(args.output).write_text(rendered)


if __name__ == "__main__":
    main()
