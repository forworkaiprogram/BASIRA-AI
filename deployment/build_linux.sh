#!/bin/bash
# Build BASIRA AI desktop for Linux (one-file binary under dist/).
set -e
cd "$(dirname "$0")/.."
python -m pip install --quiet pyinstaller
pyinstaller deployment/basira.spec --noconfirm
echo "Build output: dist/BASIRA-AI"
