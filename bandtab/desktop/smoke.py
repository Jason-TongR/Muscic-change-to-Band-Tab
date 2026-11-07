"""Executable self-test for release builds, isolated from the real user's library."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from PySide6.QtWidgets import QApplication
from bandtab.storage import Library,atomic_json
from bandtab.runtime import worker_command,process_options
from bandtab import demo,export
from .window import MainWindow


def run(root,ai=False):
    app=QApplication.instance() or QApplication([])
    report={}
    with tempfile.TemporaryDirectory(prefix='bandtab-check-') as tmp:
        library=Library(Path(tmp)/'home');folder=library.create_folder()
        p=demo.create(folder);library.save(p)
        window=MainWindow(library.root);window.open_project(p);window.resize(1320,940);window.show()
        for _ in range(10):app.processEvents();time.sleep(.03)
        assert window.table.rowCount()==192
        report['native_window']='pass'
        window.grab().save(str(Path(root)/'desktop-preview.png'))
        package=Path(tmp)/'rehearsal.bandtab';library.export_package(p,package)
        imported=library.import_package(package)
        assert imported['id']!=p['id'] and library.asset(imported).exists()
        assert export.midi(imported).startswith(b'MThd')
        report['project_roundtrip']='pass'
        target=library.create_folder()
        source=folder/'guitar.wav'
        if ai:
            from bandtab.audio import read_wav,write_wav
            y,sr=read_wav(folder/'audio.wav');source=Path(tmp)/'short.wav';write_wav(source,y[:sr],sr)
        atomic_json(target/'request.json',dict(source=str(source),title='打包程序自检',options=dict(mode='band' if ai else 'preview',bpm=108)))
        log=(target/'check.log').open('w')
        process=subprocess.Popen(worker_command('--worker',str(target/'request.json')),stdout=log,stderr=log,**process_options())
        deadline=time.monotonic()+(600 if ai else 90)
        while process.poll() is None and time.monotonic()<deadline:app.processEvents();time.sleep(.05)
        if process.poll() is None:
            (target/'cancel').touch()
            try:process.wait(timeout=60)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            raise RuntimeError('自检超时')
        log.close()
        if process.returncode:
            raise RuntimeError((target/'check.log').read_text(encoding='utf8')[-5000:])
        result=library.load(target.name)
        assert len(result['tracks'])==(6 if ai else 1)
        assert any(t['notes'] for t in result['tracks'])
        report['frozen_worker_band' if ai else 'worker_transcription']='pass'
        window.close();app.processEvents()
    atomic_json(Path(root)/'self-test-report.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0
