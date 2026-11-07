#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -x .venv-desktop/bin/python ]; then
  exec .venv-desktop/bin/python desktop.py "$@"
elif [ -x .venv-ai/bin/python ]; then
  exec .venv-ai/bin/python desktop.py "$@"
else
  exec python3 desktop.py "$@"
fi
