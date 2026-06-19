#!/usr/bin/env python3
"""Render one or more Jinja2 YAML templates from a shared context.

Usage (new multi-template form):
    render_config.py [KEY=VALUE ...] \\
        [--context-file base.json] \\
        [--dump-context out.json] \\
        [--template OUTPUT:TEMPLATE ...]

Usage (legacy single-template form, still supported):
    render_config.py <template.yaml.j2> KEY=VALUE [KEY=VALUE ...] \\
        [--output run_config.yaml]

Value coercion:
    "None" / "null"   -> None   (falsy; omits conditional blocks)
    "true" / "false"  -> bool
    digits-only        -> int
    "" (empty)         -> ""    (also falsy)
    anything else      -> str

Special key:
    dataset_dir=<path>
        Scans the directory for *.h5ad files (lexicographic order), reads
        n_obs from each via h5py, and injects:
            filenames  - list of absolute file path strings
            limits     - cumulative sum of n_obs across files
        If dataset_dir is absent, filenames=[] and limits=[] are injected
        so preview renders (without real data) produce valid YAML.

Flags:
    --context-file FILE
        Load FILE (JSON) as the base context.  CLI KEY=VALUE args still
        override individual keys.
    --dump-context FILE
        Write the fully coerced context (before dataset_dir expansion) to
        FILE as JSON.  Can be combined with --template to also render.
    --template OUTPUT:TEMPLATE  (repeatable, short: -t)
        Render TEMPLATE to OUTPUT.  All --template targets share one context
        and one dataset_dir scan.  The loader searches the directory of the
        first template provided.
    --output FILE
        Output path for the legacy positional-template form (default:
        run_config.yaml).
    --patch OUTPUT:INPUT  (repeatable, short: -p)
        Load INPUT as a pre-rendered YAML, inject filenames+limits from a
        dataset_dir scan (if dataset_dir KEY=VALUE is given), and apply any
        other KEY=VALUE overrides by matching key names recursively in the
        YAML tree.  Writes the result to OUTPUT.  No Jinja2 processing is
        performed — this is a surgical patch of an already-rendered config.
"""
import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Dataset scanning
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# YAML patching (pre-rendered configs — inject filenames/limits at runtime)
# ---------------------------------------------------------------------------

def _inject_filenames_limits(node, filenames: list, limits: list) -> bool:
    """Recursively find the first dict with a 'filenames' key and replace it."""
    if isinstance(node, dict):
        if "filenames" in node:
            node["filenames"] = filenames
            node["limits"] = limits
            return True
        for v in node.values():
            if _inject_filenames_limits(v, filenames, limits):
                return True
    elif isinstance(node, list):
        for item in node:
            if _inject_filenames_limits(item, filenames, limits):
                return True
    return False


def _replace_keys(node, overrides: dict):
    """Recursively replace values for any matching keys in the YAML tree."""
    if isinstance(node, dict):
        for k in list(node.keys()):
            if k in overrides:
                node[k] = overrides[k]
            else:
                _replace_keys(node[k], overrides)
    elif isinstance(node, list):
        for item in node:
            _replace_keys(item, overrides)


def patch_yaml(input_path: str, output_path: str, context: dict):
    """Patch a pre-rendered YAML with runtime values and write to output_path."""
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML is not installed. Run: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    with open(input_path) as f:
        data = yaml.safe_load(f)

    if "dataset_dir" in context:
        filenames, limits = dataset_dir_to_filenames_and_limits(context["dataset_dir"])
        if not _inject_filenames_limits(data, filenames, limits):
            print(f"Warning: no 'filenames' key found in {input_path} to patch",
                  file=sys.stderr)

    other = {k: v for k, v in context.items() if k != "dataset_dir"}
    if other:
        _replace_keys(data, other)

    with open(output_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    print(f"Patched {input_path} -> {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Legacy positional template (optional – new mode uses --template flags)
    parser.add_argument(
        "template_positional", nargs="?", default=None, metavar="template",
        help="Template file path (legacy positional form)",
    )
    parser.add_argument(
        "variables", nargs="*", metavar="key=value",
        help="Context variables; override --context-file values",
    )
    parser.add_argument(
        "--template", "-t", action="append", dest="extra_templates",
        metavar="OUTPUT:TEMPLATE",
        help="Render OUTPUT from TEMPLATE (repeatable)",
    )
    parser.add_argument(
        "--context-file", metavar="FILE",
        help="JSON file to load as base context (CLI key=value overrides it)",
    )
    parser.add_argument(
        "--dump-context", metavar="FILE",
        help="Write coerced context (before dataset scan) to FILE as JSON",
    )
    parser.add_argument(
        "--output", default="run_config.yaml",
        help="Output path for legacy positional-template form",
    )
    parser.add_argument(
        "--patch", "-p", action="append", dest="patches",
        metavar="OUTPUT:INPUT",
        help="Patch INPUT (pre-rendered YAML) with dataset_dir scan and key overrides, write to OUTPUT (repeatable)",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Distinguish legacy positional template from a stray key=value arg
    # that argparse grabbed as template_positional.
    # ------------------------------------------------------------------
    all_variables = list(args.variables)
    legacy_template = None

    if args.template_positional is not None:
        if "=" in args.template_positional:
            # It's actually a key=value – prepend it to variables
            all_variables = [args.template_positional] + all_variables
        else:
            legacy_template = args.template_positional

    # Build the full list of (output_path, template_path) pairs
    templates_to_render = []
    if legacy_template:
        templates_to_render.append((args.output, legacy_template))
    if args.extra_templates:
        for spec in args.extra_templates:
            output, _, template = spec.partition(":")
            if not template:
                print(f"Error: --template argument must be OUTPUT:TEMPLATE, got {spec!r}",
                      file=sys.stderr)
                sys.exit(1)
            templates_to_render.append((output, template))

    patches_to_apply = []
    if args.patches:
        for spec in args.patches:
            output, _, input_path = spec.partition(":")
            if not input_path:
                print(f"Error: --patch argument must be OUTPUT:INPUT, got {spec!r}",
                      file=sys.stderr)
                sys.exit(1)
            patches_to_apply.append((output, input_path))

    # ------------------------------------------------------------------
    # Build context
    # ------------------------------------------------------------------
    context: dict = {}

    # Base: load from --context-file if provided
    if args.context_file:
        with open(args.context_file) as fh:
            context.update(json.load(fh))

    # Override / extend with CLI key=value pairs
    for item in all_variables:
        key, _, value = item.partition("=")
        if key:
            context[key] = coerce(value)

    # ------------------------------------------------------------------
    # Optionally dump context (before dataset expansion) to JSON
    # ------------------------------------------------------------------
    if args.dump_context:
        Path(args.dump_context).write_text(json.dumps(context, indent=2, default=str))
        print(f"Context written to {args.dump_context}")

    # ------------------------------------------------------------------
    # Early exit if nothing to do
    # ------------------------------------------------------------------
    if not templates_to_render and not patches_to_apply:
        return

    # ------------------------------------------------------------------
    # Jinja2 template rendering
    # ------------------------------------------------------------------
    if templates_to_render:
        render_context = dict(context)
        if "dataset_dir" in render_context:
            dataset_dir = render_context.pop("dataset_dir")
            render_context["filenames"], render_context["limits"] = \
                dataset_dir_to_filenames_and_limits(dataset_dir)
        else:
            render_context.setdefault("filenames", [])
            render_context.setdefault("limits", [])

        try:
            from jinja2 import Environment, FileSystemLoader, StrictUndefined
        except ImportError:
            print("Error: jinja2 is not installed. Run: pip install jinja2", file=sys.stderr)
            sys.exit(1)

        first_template_path = Path(templates_to_render[0][1])
        template_dir = str(first_template_path.parent) if first_template_path.parent != Path(".") else "."
        env = Environment(
            loader=FileSystemLoader(template_dir),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

        for output_path, template_path in templates_to_render:
            tmpl = env.get_template(Path(template_path).name)
            rendered = tmpl.render(**render_context)
            Path(output_path).write_text(rendered)
            print(f"Rendered {template_path} -> {output_path}")
            print(rendered)
            print()

    # ------------------------------------------------------------------
    # YAML patching (pre-rendered configs — inject filenames/limits and
    # any other runtime key overrides without re-running Jinja2)
    # ------------------------------------------------------------------
    for output_path, input_path in patches_to_apply:
        patch_yaml(input_path, output_path, context)


if __name__ == "__main__":
    main()
