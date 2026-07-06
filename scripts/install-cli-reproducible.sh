#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

python -m pip install --upgrade pip build
python -m build packages/sdk-python
python -m build packages/cli

mkdir -p artifacts
sha256sum packages/sdk-python/dist/*.whl packages/cli/dist/*.whl > artifacts/release-checksums.sha256

python -m pip install --force-reinstall packages/sdk-python/dist/*.whl
python -m pip install --force-reinstall packages/cli/dist/*.whl

ambrosia --help > /dev/null

echo "Reproducible CLI install completed."
echo "Checksums: artifacts/release-checksums.sha256"
