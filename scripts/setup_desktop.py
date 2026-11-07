#!/usr/bin/env python3
"""Cross-platform isolated setup. Python 3.11 required; installs CPU AI + GUI."""
from pathlib import Path
import subprocess
import sys
import platform
import venv

ROOT=Path(__file__).resolve().parent.parent

def run(*args):subprocess.run([str(v) for v in args],cwd=ROOT,check=True)

def main():
    if sys.version_info[:2]!=(3,11):raise SystemExit('开发环境请使用 Python 3.11；普通用户使用打包后的程序，无需 Python。')
    env=ROOT/'.venv-desktop'
    if not env.exists():venv.EnvBuilder(with_pip=True).create(env)
    python=env/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    run(python,'-m','pip','install','--upgrade','pip')
    torch_version='2.2.2' if sys.platform=='darwin' and platform.machine()=='x86_64' else '2.5.1'
    args=[f'torch=={torch_version}',f'torchaudio=={torch_version}']
    if sys.platform!='darwin':args+=['--index-url','https://download.pytorch.org/whl/cpu']
    run(python,'-m','pip','install',*args)
    # Use ONNX on all platforms. No TensorFlow/CoreML runtime is needed for this app.
    run(python,'-m','pip','install','numpy==1.26.4','scipy==1.13.1','librosa==0.10.2.post1',
        'onnxruntime==1.20.1','demucs==4.0.1','resampy==0.4.2','pretty_midi>=0.2.10,<0.3',
        'mir_eval>=0.7,<1','scikit-learn>=1.5,<2','setuptools==80.9.0',
        '-r','requirements-desktop.txt','-r','requirements-build.txt')
    run(python,'-m','pip','install','basic-pitch==0.4.0','--no-deps')
    run(python,'-c','from basic_pitch.inference import Model; import demucs, PySide6, torch, torchaudio')
    print('桌面开发环境就绪。运行：',python,'desktop.py')

if __name__=='__main__':main()
