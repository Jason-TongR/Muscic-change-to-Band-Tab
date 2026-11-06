#!/usr/bin/env bash
# Isolated interpreter and packages. Does not alter system Python or require sudo.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
export UV_PYTHON_INSTALL_DIR="$ROOT/.python"
export UV_CACHE_DIR="$ROOT/.cache/uv"
export PIP_CACHE_DIR="$ROOT/.cache/pip"
if command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
elif [ -x "$ROOT/.tools/bin/uv" ]; then
  UV="$ROOT/.tools/bin/uv"
else
  python3 -m pip install --target .tools uv
  UV="$ROOT/.tools/bin/uv"
fi
if [ ! -x .venv-ai/bin/python ]; then
  "$UV" venv --python 3.11 .venv-ai
fi
"$UV" pip install --python .venv-ai/bin/python 'torch==2.5.1' 'torchaudio==2.5.1' --index-url https://download.pytorch.org/whl/cpu
"$UV" pip install --python .venv-ai/bin/python -r requirements-ai.txt
.venv-ai/bin/python -c 'import numpy, scipy, torch, torchaudio, librosa, basic_pitch, onnxruntime, demucs; from basic_pitch.inference import Model'
touch .venv-ai/.bandtab-ready
printf '\nAI 模式已安装。首次分轨将下载模型。运行：bash scripts/start.sh\n'
