#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -x .venv-ai/bin/python ] && [ -f .venv-ai/.bandtab-ready ]; then
  exec .venv-ai/bin/python app.py "$@"
elif [ -x .venv/bin/python ]; then
  exec .venv/bin/python app.py "$@"
else
  exec python3 app.py "$@"
fi
