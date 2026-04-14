#!/usr/bin/env bash
# Install cellarium-ml from GitHub at a specific git ref (tag, branch, or SHA).
# Usage: maybe_pip_install.sh <ref>
#
# If <ref> is empty or the string "null", this script is a no-op and the
# version already present in the container image is used unchanged.

set -euo pipefail

ref="${1:-}"

if [ -z "$ref" ] || [ "$ref" = "null" ]; then
    exit 0
fi

pip install "git+https://github.com/cellarium-ai/cellarium-ml.git@${ref}"
