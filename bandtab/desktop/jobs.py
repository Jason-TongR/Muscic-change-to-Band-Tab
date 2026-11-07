"""GUI stays responsive: inference in a process; package/model I/O in a thread."""
import json
from pathlib import Path
import subprocess
import threading
import traceback
from PySide6.QtCore import QObject, Signal, QTimer, QThread
from bandtab.storage import atomic_json
from bandtab.runtime import worker_command, process_options
from bandtab.pipeline import Cancelled


class TaskThread(QThread):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(int,str)
    def __init__(self,fn,parent=None):
        super().__init__(parent);self.fn=fn;self.cancelled=threading.Event()
    def check(self):
        if self.cancelled.is_set():raise Cancelled()
    def run(self):
        try:self.result.emit(self.fn(self.progress.emit,self.check))
        except Cancelled:self.error.emit('任务已取消')
        except Exception as e:self.error.emit(str(e))


class InferenceJob(QObject):
    progress=Signal(int,str)
    result=Signal(object)
    error=Signal(str)
    finished=Signal()
    def __init__(self,library,source,options,parent=None):
        super().__init__(parent)
        self.folder=library.create_folder();self.library=library
        atomic_json(self.folder/'request.json',dict(source=str(Path(source).resolve()),options=options,title=Path(source).stem))
        self.log=(self.folder/'worker.log').open('w',encoding='utf8')
        try:
            self.process=subprocess.Popen(worker_command('--worker',str(self.folder/'request.json')),
                                          stdout=self.log,stderr=self.log,**process_options())
        except Exception:self.log.close();raise
        self.timer=QTimer(self);self.timer.setInterval(300);self.timer.timeout.connect(self.poll);self.timer.start()
        self.cancelling=False
    def cancel(self):
        self.cancelling=True;(self.folder/'cancel').touch()
        self.progress.emit(-1,'正在停止：等待当前推理片段结束…')
    def poll(self):
        state={}
        try:state=json.loads((self.folder/'status.json').read_text(encoding='utf8'))
        except (OSError,ValueError):pass
        if state and not self.cancelling:self.progress.emit(state.get('progress',0),state.get('message','处理中'))
        code=self.process.poll()
        if code is None:return
        self.timer.stop();self.log.close()
        try:
            if code==0 and (self.folder/'project.json').exists():self.result.emit(self.library.load(self.folder.name))
            else:self.error.emit(state.get('message') or f'识别进程退出（{code}）。日志：{self.folder / "worker.log"}')
        finally:self.finished.emit()
