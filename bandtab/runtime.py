"""Frozen/source worker commands and model cache management."""
import hashlib
import os
from pathlib import Path
import shutil
import sys
import urllib.request

MODEL_FILE = '5c90dfd2-34c22ccb.th'
MODEL_URL = 'https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/'+MODEL_FILE


def resources():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def worker_command(*args):
    if getattr(sys, 'frozen', False): return [sys.executable, *args]
    return [sys.executable, str(resources()/'desktop.py'), *args]


def process_options():
    return {'creationflags': 0x08000000} if os.name == 'nt' else {}


def model_path():
    base = Path(os.environ.get('BANDTAB_MODEL_HOME', resources()/'data'/'models'))
    return base/'hub'/'checkpoints'/MODEL_FILE


def valid_model(path):
    path = Path(path)
    if not path.is_file(): return False
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):digest.update(chunk)
    return digest.hexdigest().startswith('34c22ccb')


def ensure_model(update=lambda *args:None, check=lambda:None):
    target = model_path()
    if valid_model(target):update(100, '分轨模型已就绪');return target
    target.parent.mkdir(parents=True, exist_ok=True)
    bundled = resources()/'bundled_models'/MODEL_FILE
    if valid_model(bundled):
        shutil.copy2(bundled,target);update(100,'已启用随软件提供的离线模型');return target
    partial = target.with_suffix('.download')
    try:
        update(0,'正在下载分轨模型（约 55 MB）')
        with urllib.request.urlopen(MODEL_URL, timeout=30) as r, partial.open('wb') as out:
            total = int(r.headers.get('Content-Length', 55000000));done = 0
            while True:
                check();chunk = r.read(256*1024)
                if not chunk: break
                out.write(chunk);done += len(chunk)
                update(min(98, int(done/max(total,1)*100)), f'下载模型 {done/1024**2:.1f} / {total/1024**2:.1f} MB')
        if not valid_model(partial): raise ValueError('模型校验失败，请重试下载')
        os.replace(partial,target);update(100,'模型已下载并校验');return target
    finally:
        if partial.exists():partial.unlink()
