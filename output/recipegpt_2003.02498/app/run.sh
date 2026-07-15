#!/usr/bin/env bash
# run.sh — RecipeGPT CLI quickstart (Linux/macOS)
# Usage:  ./run.sh          # dependency-free evaluation demo
#         ./run.sh --gen    # also install torch/transformers + real GPT-2 gen
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! "$PY" -c 'import sys; assert sys.version_info>=(3,9)' 2>/dev/null; then
  echo "python 3.9+ required" >&2; exit 1
fi

echo "== Evaluation module (no heavy deps) =="
"$PY" main.py --mode evaluate

echo
echo "== Similar-recipe retrieval: BM25 + TF-IDF (no heavy deps) =="
"$PY" main.py --mode retrieve

if [[ "${1:-}" == "--gen" ]]; then
  echo
  echo "== Installing generation deps (torch, transformers) =="
  "$PY" -m pip install -r requirements.txt
  echo
  echo "== Real GPT-2 inference: instructions from title+ingredients =="
  "$PY" main.py --mode gen-instructions
  echo
  echo "== Live perplexity (companion to paper PPL 3.70) =="
  "$PY" main.py --mode perplexity
fi
