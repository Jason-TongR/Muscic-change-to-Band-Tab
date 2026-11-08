"""Executable checks that preserve a report even when a windowed EXE fails."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import traceback
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from bandtab.storage import Library,atomic_json
from bandtab.runtime import worker_command,process_options
from bandtab import demo,export
from .window import MainWindow


def run(root,ai=False):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    report_path=root/'self-test-report.json'
    report_path.unlink(missing_ok=True)
    app=QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    report={};window=None;target=None
    try:
        with tempfile.TemporaryDirectory(prefix='BandTab 中文 路径 ') as tmp:
            try:
                library=Library(Path(tmp)/'home');folder=library.create_folder()
                project=demo.create(folder);library.save(project)
                window=MainWindow(library.root);window.open_project(project)
                window.resize(1320,940);window.show()
                for _ in range(10):app.processEvents();time.sleep(.03)
                assert window.table.rowCount()==192
                report['native_window']='pass'
                assert window.grab().save(str(root/'desktop-preview.png'))
                package=Path(tmp)/'原创 练习.bandtab';library.export_package(project,package)
                imported=library.import_package(package)
                assert imported['id']!=project['id'] and library.asset(imported).exists()
                assert export.midi(imported).startswith(b'MThd')
                report['project_roundtrip']='pass'
                target=library.create_folder()
                source=folder/'guitar.wav'
                if ai:
                    from bandtab.audio import read_wav,write_wav
                    y,sr=read_wav(folder/'audio.wav');source=Path(tmp)/'AI 输入.wav'
                    write_wav(source,y[:sr],sr)
                atomic_json(target/'request.json',dict(source=str(source),title='打包程序自检',
                    options=dict(mode='band' if ai else 'preview',bpm=108)))
                with (root/'worker-check.log').open('w',encoding='utf8') as log:
                    process=subprocess.Popen(worker_command('--worker',str(target/'request.json')),
                        stdout=log,stderr=log,**process_options())
                    deadline=time.monotonic()+(600 if ai else 90)
                    last_status=None
                    while process.poll() is None and time.monotonic()<deadline:
                        status_file=target/'status.json'
                        if status_file.exists():
                            status=status_file.read_text(encoding='utf8')
                            if status!=last_status:
                                print(json.dumps(json.loads(status),ensure_ascii=True),flush=True);last_status=status
                        app.processEvents();time.sleep(.05)
                    if process.poll() is None:
                        (target/'cancel').touch()
                        try:process.wait(timeout=60)
                        except subprocess.TimeoutExpired:
                            if os.name=='nt':
                                subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),
                                    '/PID',str(process.pid),'/T','/F'],capture_output=True,**process_options())
                            else:process.kill()
                            process.wait(timeout=10)
                        raise RuntimeError('自检超时')
                for name in ('error.log','separation.log'):
                    if (target/name).is_file():(root/name).write_bytes((target/name).read_bytes())
                if process.returncode:
                    raise RuntimeError((root/'worker-check.log').read_text(encoding='utf8',errors='replace')[-5000:])
                result=library.load(target.name)
                assert len(result['tracks'])==(6 if ai else 1)
                assert any(t['notes'] for t in result['tracks'])
                report['frozen_worker_band' if ai else 'worker_transcription']='pass'
                report['unicode_paths']='pass'
            finally:
                # Keep evidence before TemporaryDirectory cleans up a failed job.
                if target:
                    for name in ('error.log','separation.log','status.json'):
                        if (target/name).is_file():
                            (root/('worker-status.json' if name=='status.json' else name)).write_bytes((target/name).read_bytes())
                if window:
                    window.close();window.deleteLater();app.processEvents()
                    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        report['temporary_files_released']='pass'
        atomic_json(report_path,report)
        print(json.dumps(report,ensure_ascii=False),flush=True)
        return 0
    except Exception:
        report['error']=traceback.format_exc()
        atomic_json(report_path,report)
        print(json.dumps(report,ensure_ascii=False),flush=True)
        return 1
