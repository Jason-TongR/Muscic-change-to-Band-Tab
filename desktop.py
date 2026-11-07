#!/usr/bin/env python3
"""Native application entry, also used for isolated frozen inference workers."""
import os
from pathlib import Path
import sys


def configure():
    from bandtab.storage import user_data_dir
    root = user_data_dir()
    root.mkdir(parents=True, exist_ok=True)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMBA_NUM_THREADS'):
        os.environ.setdefault(key, str(min(4,os.cpu_count() or 1)))
    os.environ.setdefault('NUMBA_CACHE_DIR',str(root/'cache'/'numba'))
    os.environ.setdefault('MPLCONFIGDIR',str(root/'cache'/'matplotlib'))
    os.environ.setdefault('BANDTAB_MODEL_HOME',str(root/'models'))
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
    # A windowed executable has no console on Windows. Third-party libraries print.
    if sys.stdout is None or sys.stderr is None:
        log = open(root/'desktop.log','a',encoding='utf8',buffering=1)
        if sys.stdout is None:sys.stdout = log
        if sys.stderr is None:sys.stderr = log
    return root


def worker(request_path):
    import json, traceback
    from bandtab.pipeline import transcribe, Cancelled
    from bandtab.storage import atomic_json
    request_path = Path(request_path)
    raw = json.loads(request_path.read_text(encoding='utf8'))
    folder = request_path.parent
    def update(n, message): atomic_json(folder/'status.json',dict(status='running',progress=n,message=message))
    def check():
        if (folder/'cancel').exists(): raise Cancelled()
    try:
        check()
        p = transcribe(Path(raw['source']), folder, raw['options'], update, check)
        p['title'] = raw['title']
        check();atomic_json(folder/'project.json',p)
        atomic_json(folder/'status.json',dict(status='done',progress=100,message='转写完成'))
        return 0
    except Cancelled:
        atomic_json(folder/'status.json',dict(status='cancelled',progress=0,message='任务已取消'))
        return 2
    except BaseException as e:
        (folder/'error.log').write_text(traceback.format_exc(),encoding='utf8')
        atomic_json(folder/'status.json',dict(status='error',progress=0,message=str(e)))
        return 1


def main():
    import multiprocessing
    multiprocessing.freeze_support()
    root = configure()
    if len(sys.argv)>1 and sys.argv[1]=='--worker':return worker(sys.argv[2])
    if len(sys.argv)>1 and sys.argv[1]=='--demucs-worker':
        from demucs.separate import main as separate
        separate(sys.argv[2:]);return 0
    if len(sys.argv)>1 and sys.argv[1]=='--self-test':
        from bandtab.desktop.smoke import run
        return run(root, ai='--ai' in sys.argv)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QTimer
    from bandtab.desktop.window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName('BandTab Studio');app.setOrganizationName('BandTab')
    app.setStyle('Fusion')
    window = MainWindow(root)
    window.show()
    if '--demo' in sys.argv:QTimer.singleShot(0,window.open_demo)
    elif '--open' in sys.argv:
        index=sys.argv.index('--open')
        if index+1<len(sys.argv):QTimer.singleShot(0,lambda:window.open_file(sys.argv[index+1]))
    elif len(sys.argv)>1 and Path(sys.argv[1]).is_file():
        QTimer.singleShot(0,lambda:window.open_file(sys.argv[1]))
    return app.exec()


if __name__=='__main__':raise SystemExit(main())
