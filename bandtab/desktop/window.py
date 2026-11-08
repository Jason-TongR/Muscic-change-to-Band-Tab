"""BandTab Studio native workspace; all actions operate on local projects."""
import copy
from pathlib import Path
import uuid
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QKeySequence, QDesktopServices, QShortcut, QIcon
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QListWidget,QListWidgetItem,QSplitter,QFrame,QScrollArea,QComboBox,QSlider,QCheckBox,
    QProgressBar,QFileDialog,QMessageBox,QDialog,QTabWidget,QTableWidget,QTableWidgetItem,
    QAbstractItemView,QHeaderView,QMenu,QSizePolicy)
from bandtab.storage import Library
from bandtab.score import validate_project,note_name
from bandtab.pipeline import capabilities
from bandtab.runtime import ensure_model,model_path,valid_model,resources
from bandtab import demo,export
from .widgets import ScoreCanvas,Waveform,clock
from .playback import Transport
from .jobs import InferenceJob,TaskThread
from .dialogs import ImportDialog,NoteDialog,SettingsDialog

STYLE='''
QWidget { background:#131710; color:#e5eddd; font-size:13px; }
QMainWindow, QDialog { background:#131710; }
QLabel { background:transparent; }
QLabel#brand { font-size:25px; font-weight:700; color:#c3ee87; }
QLabel#title { font-size:27px; font-weight:600; }
QLabel#dialogTitle { font-size:22px; padding:12px 0; }
QLabel#muted { color:#98a48b; font-size:12px; }
QLabel#notice { background:#252f1d; border:1px solid #405331; border-radius:6px; padding:10px; color:#c4d1b8; }
QLabel#error { color:#efb38d; }
QPushButton { background:#27321f; border:1px solid #405131; padding:9px 13px; border-radius:6px; }
QPushButton:hover { background:#35472a; }
QPushButton:pressed,QPushButton:checked { background:#506935; color:#e6ffb8; }
QPushButton:disabled { color:#637058; background:#1b2216; border-color:#2c3625; }
QPushButton#primary { color:#17200f; background:#c3ee87; border-color:#c3ee87; font-weight:600; }
QPushButton#mini { padding:0; min-width:28px; max-width:28px; }
QPushButton#play { background:#c3ee87; color:#14200c; font-size:20px; border-radius:22px; }
QListWidget { border:0; background:#192015; outline:0; }
QListWidget::item { padding:14px 10px; margin:3px; border-radius:5px; }
QListWidget::item:selected { background:#33452a; color:#dbf6bb; }
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox { background:#1a2215; border:1px solid #435336; padding:7px; border-radius:4px; }
QComboBox QAbstractItemView { selection-background-color:#3d522c; }
QCheckBox { spacing:7px; background:transparent; }
QCheckBox::indicator { width:15px; height:15px; border:1px solid #6a8058; border-radius:3px; background:#20291a; }
QCheckBox::indicator:checked { background:#c3ee87; }
QSlider::groove:horizontal { height:5px; background:#38472c; border-radius:2px; }
QSlider::handle:horizontal { width:13px; margin:-4px 0; border-radius:6px; background:#c3ee87; }
QScrollArea { border:1px solid #35452b; border-radius:6px; }
QScrollBar:horizontal { height:10px; background:#1a2314; }
QScrollBar:vertical { width:10px; background:#1a2314; }
QScrollBar::handle { background:#526b3e; border-radius:4px; min-width:20px; min-height:20px; }
QScrollBar::add-line,QScrollBar::sub-line { height:0; width:0; }
QTabWidget::pane { border:0; }
QTabBar::tab { background:#202a19; padding:10px 18px; margin-right:5px; border-radius:4px; }
QTabBar::tab:selected { background:#3e522e; color:#d8f6b3; }
QTableWidget { background:#182013; alternate-background-color:#202a19; border:1px solid #35452b; gridline-color:#35452b; }
QHeaderView::section { background:#293720; padding:9px; border:0; }
QProgressBar { border:1px solid #455a33; border-radius:4px; background:#202a19; text-align:center; }
QProgressBar::chunk { background:#6d9149; }
QMenu { border:1px solid #526640; background:#202b19; }
QMenu::item { padding:9px 22px; } QMenu::item:selected { background:#3a5129; }
QStatusBar { color:#98a48b; }
QSplitter::handle { background:#303e24; }
'''


def button(text,fn=None,primary=False):
    b=QPushButton(text)
    if fn:b.clicked.connect(fn)
    if primary:b.setObjectName('primary')
    return b


def label(text,name=None):
    w=QLabel(text)
    if name:w.setObjectName(name)
    return w


class MainWindow(QMainWindow):
    def __init__(self,root=None):
        super().__init__();self.setWindowTitle('BandTab Studio · 桌面排练室');self.resize(1320,900);self.setMinimumSize(960,700)
        self.setStyleSheet(STYLE);self.setAcceptDrops(True);self.setWindowIcon(QIcon(str(resources()/'assets'/'icon.png')))
        self.library=Library(root);self.project=None;self.baseline=None;self.dirty=False;self.undo_stack=[]
        self.job=None;self.task=None;self.quit_after=False;self.a=None;self.b=None;self.loop_enabled=False
        self.transport=Transport(self);self.transport.position.connect(self.on_position)
        self.transport.playing.connect(lambda p:self.play_button.setText('Ⅱ' if p else '▶'))
        self.transport.error.connect(self.status_message)
        self.build();self.refresh_library();self.set_project_enabled(False)
        QShortcut(QKeySequence('Ctrl+O'),self,activated=self.import_audio)
        QShortcut(QKeySequence('Ctrl+S'),self,activated=self.save_action)
        QShortcut(QKeySequence('Ctrl+Z'),self,activated=self.undo)
        self.statusBar().showMessage('准备就绪。拖入音频或完整 .bandtab 项目包。')
    def build(self):
        split=QSplitter();self.setCentralWidget(split)
        side=QWidget();side.setMinimumWidth(215);side.setMaximumWidth(290)
        sl=QVBoxLayout(side);sl.setContentsMargins(18,24,18,18);sl.setSpacing(16)
        sl.addWidget(label('≋  BandTab','brand'));sl.addWidget(label('STUDIO  /  桌面排练室','muted'))
        self.import_button=button('＋ 导入音乐',self.import_audio,True);sl.addWidget(self.import_button)
        self.open_button=button('打开分享项目…',self.open_file);sl.addWidget(self.open_button)
        sl.addWidget(label('你的曲库','muted'));self.list=QListWidget();self.list.setAccessibleName('项目曲库')
        self.list.itemClicked.connect(lambda item:self.open_library(item.data(Qt.ItemDataRole.UserRole)));sl.addWidget(self.list,1)
        sl.addWidget(button('♫  原创练习曲',self.open_demo));sl.addWidget(button('引擎与离线模型',self.engine_dialog))
        sl.addWidget(button('打开数据文件夹',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.library.root)))))
        sl.addWidget(button('使用说明',self.help_dialog))
        caps=capabilities();sl.addWidget(label('● 音频在本机处理\n'+('AI 引擎已安装' if caps['basic_pitch'] and caps['demucs'] else '基础引擎已安装'),'muted'))
        split.addWidget(side)
        main=QWidget();outer=QVBoxLayout(main);outer.setContentsMargins(24,22,24,12);outer.setSpacing(12)
        top=QHBoxLayout();top.addWidget(label('WORKSPACE  /  乐队动态谱','muted'));top.addStretch()
        self.save_button=button('保存',self.save_action);top.addWidget(self.save_button)
        self.share_button=button('分享完整项目',self.share);top.addWidget(self.share_button)
        self.export_button=button('导出谱子 ▾');menu=QMenu(self)
        for title,fmt in [('MIDI · 实际时值','midi'),('MusicXML · 量化谱面','musicxml'),('文本六线谱','txt')]:
            action=menu.addAction(title);action.triggered.connect(lambda checked=False,f=fmt:self.export_score(f))
        self.export_button.setMenu(menu);top.addWidget(self.export_button);outer.addLayout(top)
        self.title=label('把喜欢的音乐，带进下一次合奏。','title');outer.addWidget(self.title)
        meta=QHBoxLayout();self.meta=label('导入 → 转写 → 校正 → 跟弹 → 分享','muted');meta.addWidget(self.meta);meta.addStretch()
        self.settings_button=button('节拍校正',self.settings);meta.addWidget(self.settings_button);outer.addLayout(meta)
        self.notice=label('先打开原创演示，体验动态跟谱。完整项目包包含音频和谱子，发给别人就能继续排练。','notice');self.notice.setWordWrap(True);outer.addWidget(self.notice)
        transport=QHBoxLayout();self.play_button=button('▶',self.transport.toggle);self.play_button.setObjectName('play');self.play_button.setFixedSize(46,46);self.play_button.setAccessibleName('播放或暂停');transport.addWidget(self.play_button)
        self.time=label('0:00.0 / 0:00.0');self.time.setMinimumWidth(122);transport.addWidget(self.time)
        transport.addWidget(label('速度','muted'));self.speed=QComboBox()
        for rate in (.5,.65,.75,.85,1.,1.25):self.speed.addItem(f'{rate:g}×',rate)
        self.speed.setCurrentIndex(4);self.speed.currentIndexChanged.connect(lambda:self.transport.set_rate(self.speed.currentData()));transport.addWidget(self.speed)
        self.a_button=button('A 起点',self.set_a);self.b_button=button('B 终点',self.set_b);self.loop_button=button('↻ 循环',self.toggle_loop);self.loop_button.setCheckable(True)
        for b in (self.a_button,self.b_button,self.loop_button):transport.addWidget(b)
        transport.addStretch();self.follow=QCheckBox('自动跟谱');self.follow.setChecked(True);transport.addWidget(self.follow);outer.addLayout(transport)
        self.wave=Waveform();self.wave.seek.connect(self.transport.seek);outer.addWidget(self.wave)
        self.seek=QSlider(Qt.Orientation.Horizontal);self.seek.setAccessibleName('播放位置');self.seek.setRange(0,1)
        self.seek.sliderMoved.connect(lambda pos:self.transport.seek(pos/1000));self.seek.sliderReleased.connect(lambda:self.transport.seek(self.seek.value()/1000));outer.addWidget(self.seek)
        controls=QHBoxLayout();controls.addWidget(label('乐队总谱'));self.track=QComboBox();self.track.setMinimumWidth(140);self.track.currentIndexChanged.connect(self.filter_track);controls.addWidget(self.track)
        controls.addWidget(label('缩放','muted'));self.zoom=QSlider(Qt.Orientation.Horizontal);self.zoom.setRange(50,210);self.zoom.setValue(95);self.zoom.setMaximumWidth(105);self.zoom.valueChanged.connect(self.zoom_score);controls.addWidget(self.zoom)
        controls.addStretch();self.review=QCheckBox('突出待复核');self.review.toggled.connect(self.highlight_review);controls.addWidget(self.review)
        self.add_button=button('＋ 音符',self.add_note);controls.addWidget(self.add_button)
        self.undo_button=button('↶ 撤销',self.undo);controls.addWidget(self.undo_button);outer.addLayout(controls)
        self.tabs=QTabWidget();self.scroll=QScrollArea();self.scroll.setWidgetResizable(False);self.canvas=ScoreCanvas();self.scroll.setWidget(self.canvas)
        self.canvas.edit.connect(self.edit_note);self.canvas.seek.connect(self.transport.seek);self.tabs.addTab(self.scroll,'动态谱')
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['声部','开始 / 秒','结束 / 秒','音高','弦 / 品','力度','复核'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.table_edit);self.table.itemActivated.connect(lambda item:self.table_edit(item.row(),item.column()))
        self.tabs.addTab(self.table,'音符清单 · 双击或回车编辑');outer.addWidget(self.tabs,1)
        outer.addWidget(label('上方为 1 弦 · 品位相对变调夹 · 橙色需复核 · 点击音符改谱','muted'))
        mixer_head=QHBoxLayout();mixer_head.addWidget(label('分轨调音台'));mixer_head.addStretch();self.stem_toggle=QCheckBox('使用分轨试听（关闭时播放原曲）');self.stem_toggle.toggled.connect(self.transport.set_stems);mixer_head.addWidget(self.stem_toggle);outer.addLayout(mixer_head)
        self.mixer_host=QWidget();self.mixer=QHBoxLayout(self.mixer_host);self.mixer.setContentsMargins(0,0,0,0);outer.addWidget(self.mixer_host)
        self.job_host=QWidget();jl=QVBoxLayout(self.job_host);jl.setContentsMargins(0,0,0,0);row=QHBoxLayout();self.job_label=QLabel();row.addWidget(self.job_label,1);self.cancel_button=button('取消任务',self.cancel_task);row.addWidget(self.cancel_button);jl.addLayout(row);self.progress=QProgressBar();jl.addWidget(self.progress);self.job_host.hide();outer.addWidget(self.job_host)
        split.addWidget(main);split.setStretchFactor(1,1);split.setSizes([235,1085])
    def set_project_enabled(self,enabled):
        for w in (self.save_button,self.share_button,self.export_button,self.settings_button,self.play_button,self.speed,self.a_button,self.b_button,self.loop_button,self.seek,self.add_button,self.undo_button,self.track,self.stem_toggle):w.setEnabled(enabled)
        self.undo_button.setEnabled(enabled and bool(self.undo_stack));self.save_button.setEnabled(enabled and self.dirty)
    def status_message(self,message):self.statusBar().showMessage(str(message),12000)
    def error(self,message):
        self.status_message(message);QMessageBox.warning(self,'无法完成',str(message))
    def guarded(self,fn):
        try:return fn()
        except Exception as e:self.error(e)
    def busy(self):return self.job is not None or self.task is not None
    def refresh_library(self):
        self.list.clear()
        for p in self.library.entries():
            item=QListWidgetItem(f"{p['title']}\n{p['bpm']:g} BPM · {clock(p['duration'])}");item.setData(Qt.ItemDataRole.UserRole,p['id']);item.setToolTip(p['title']);self.list.addItem(item)
            if self.project and p['id']==self.project['id']:self.list.setCurrentItem(item)
    def open_project(self,p):
        if self.dirty:self.save_current()
        self.project=p;self.baseline=copy.deepcopy(p);self.dirty=False;self.undo_stack=[];self.a=None;self.b=None;self.loop_enabled=False
        self.transport.load(p,self.library);self.loop_button.setChecked(False);self.stem_toggle.setChecked(False);self.a_button.setText('A 起点');self.b_button.setText('B 终点')
        self.track.blockSignals(True);self.track.clear();self.track.addItem('全部声部','all')
        for t in p['tracks']:self.track.addItem(t['name'],t['id'])
        self.track.blockSignals(False);self.canvas.track_id='all';self.canvas.position=0;self.canvas.set_project(p);self.scroll.horizontalScrollBar().setValue(0)
        self.wave.project=p;self.wave.position=0;self.wave.loop=(None,None);self.wave.update();self.seek.setRange(0,int(p['duration']*1000));self.seek.setValue(0)
        self.render_header();self.render_table();self.render_mixer();self.set_project_enabled(True);self.refresh_library()
    def open_library(self,pid):self.guarded(lambda:self.open_project(self.library.load(pid)))
    def render_header(self):
        p=self.project;self.title.setText(p['title']+(' *' if self.dirty else ''))
        count=sum(len(t['notes']) for t in p['tracks']);self.meta.setText(f"{p['bpm']:g} BPM  ·  {p['meter']}/4  ·  {clock(p['duration'])}  ·  {count} 个音符")
        self.notice.setText('原创合成演示：谱子预先编写，不代表自动识别准确度。' if p['mode']=='demo' else '基础单音参考：没有分离声部，所有音符建议复核。' if p['mode']=='preview' else 'AI 转写草稿：先复核重拍、音高和指法。鼓谱只有三种参考鼓点，复杂叠录仍需听辨。')
    def render_table(self):
        if not self.project:return
        rows=[(t,n) for t in self.project['tracks'] if self.canvas.track_id in ('all',t['id']) for n in t['notes']]
        self.table.setUpdatesEnabled(False);self.table.setRowCount(len(rows))
        for row,(t,n) in enumerate(rows):
            values=[t['name'],f"{n['start']:.3f}",f"{n['end']:.3f}",f"{note_name(n['pitch'])} ({n['pitch']})",f"{n['string']} 弦 / {n['fret']} 品" if n.get('string') else '—',str(n['velocity']),'待复核' if n.get('review') else '已确认 / 高分候选']
            for col,value in enumerate(values):
                item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,(t['id'],n['id']));self.table.setItem(row,col,item)
        self.table.setUpdatesEnabled(True)
    def render_mixer(self):
        while self.mixer.count():
            item=self.mixer.takeAt(0)
            if item.widget():item.widget().deleteLater()
        for t in self.project['tracks']:
            box=QWidget();layout=QVBoxLayout(box);layout.setContentsMargins(5,4,5,4)
            row=QHBoxLayout();row.addWidget(label(t['name'].split(' · ')[0]));row.addStretch()
            for key,text in [('mute','M'),('solo','S')]:
                b=QPushButton(text);b.setObjectName('mini');b.setFixedWidth(30);b.setCheckable(True);b.setToolTip('静音' if key=='mute' else '独奏');b.setAccessibleName(t['name']+b.toolTip())
                b.toggled.connect(lambda value,tid=t['id'],k=key:self.mix_value(tid,k,value));row.addWidget(b)
            layout.addLayout(row);volume=QSlider(Qt.Orientation.Horizontal);volume.setRange(0,100);volume.setValue(85);volume.setAccessibleName(t['name']+'音量')
            volume.valueChanged.connect(lambda value,tid=t['id']:self.mix_value(tid,'volume',value/100));layout.addWidget(volume);self.mixer.addWidget(box,1)
    def mix_value(self,track,key,value):
        self.transport.mixer[track][key]=value;self.stem_toggle.setChecked(True);self.transport.volumes()
    def on_position(self,seconds):
        if not self.project:return
        self.time.setText(f'{clock(seconds)} / {clock(self.project["duration"])}')
        if not self.seek.isSliderDown():self.seek.setValue(int(seconds*1000))
        self.wave.position=seconds;self.wave.update();self.canvas.position=seconds;self.canvas.update()
        if self.follow.isChecked() and self.transport.is_playing():
            bar=self.scroll.horizontalScrollBar();x=self.canvas.x(seconds);width=self.scroll.viewport().width()
            if x>bar.value()+width*.8 or x<bar.value()+80:bar.setValue(max(0,int(x-width*.25)))
    def set_a(self):
        self.a=self.transport.seconds()
        if self.b is not None and self.b<=self.a:self.b=None;self.loop_enabled=False
        self.update_loop()
    def set_b(self):
        b=self.transport.seconds();a=self.a if self.a is not None else 0
        if b<=a+.1:self.status_message('B 点必须在 A 点之后至少 0.1 秒');return
        self.a=a;self.b=b;self.update_loop()
    def toggle_loop(self):
        if self.a is None or self.b is None:self.loop_button.setChecked(False);self.status_message('请先设置 A 起点、B 终点');return
        self.loop_enabled=self.loop_button.isChecked();self.update_loop()
        if self.loop_enabled:self.transport.seek(self.a)
    def update_loop(self):
        self.loop_button.setChecked(self.loop_enabled);self.transport.loop=(self.a,self.b) if self.loop_enabled else None
        self.a_button.setText('A 起点' if self.a is None else 'A '+clock(self.a));self.b_button.setText('B 终点' if self.b is None else 'B '+clock(self.b));self.wave.loop=(self.a,self.b);self.wave.update()
    def zoom_score(self,value):self.canvas.scale=value;self.canvas.relayout()
    def filter_track(self):
        self.canvas.track_id=self.track.currentData() or 'all';self.canvas.relayout();self.render_table()
    def highlight_review(self,value):self.canvas.review_only=value;self.canvas.update()
    def snapshot(self):
        self.undo_stack.append(copy.deepcopy(self.project));self.undo_stack=self.undo_stack[-30:]
    def changed(self):
        self.dirty=True;self.canvas.project=self.project;self.canvas.update();self.render_header();self.render_table();self.set_project_enabled(True)
    def edit_note(self,tid,nid):
        self.transport.pause();t=next(t for t in self.project['tracks'] if t['id']==tid);n=next(n for n in t['notes'] if n['id']==nid)
        dialog=NoteDialog(t,n,self.project['duration'],self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.snapshot()
            if dialog.deleted:t['notes'].remove(n)
            else:t['notes'][t['notes'].index(n)]=dialog.result_note
            self.changed()
    def table_edit(self,row,col):
        item=self.table.item(row,col)
        if item:self.edit_note(*item.data(Qt.ItemDataRole.UserRole))
    def add_note(self):
        if not self.project:return
        tid=self.track.currentData();t=next((t for t in self.project['tracks'] if tid in ('all',t['id']) and t['instrument']!='other'),None)
        if not t:self.status_message('请选择可编辑的乐器声部');return
        start=min(self.transport.seconds(),self.project['duration']-.1)
        note=dict(id='manual-'+uuid.uuid4().hex,start=start,end=min(start+.25,self.project['duration']),pitch=t['tuning'][-1]+t.get('capo',0) if t.get('tuning') else 36 if t['instrument']=='drums' else 60,velocity=90,confidence=1,review=False,string=None,fret=None)
        dialog=NoteDialog(t,note,self.project['duration'],self);dialog.delete.hide()
        if dialog.exec()==QDialog.DialogCode.Accepted:self.snapshot();t['notes'].append(dialog.result_note);self.changed()
    def undo(self):
        if self.undo_stack:self.project=self.undo_stack.pop();self.changed()
    def save_current(self):
        if not self.project:return
        self.project=validate_project(self.project,self.baseline);self.library.save(self.project);self.baseline=copy.deepcopy(self.project);self.dirty=False
        self.canvas.set_project(self.project);self.render_header();self.render_table();self.set_project_enabled(True);self.refresh_library()
    def save_action(self):self.guarded(self.save_current)
    def settings(self):
        dialog=SettingsDialog(self.project,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.snapshot();self.project.update(title=dialog.title.text(),bpm=dialog.bpm.value(),meter=dialog.meter.value(),offset=dialog.offset.value());self.changed();self.save_action()
    def show_job(self,n,message):
        self.job_host.show();self.job_label.setText(message);self.progress.setRange(0,0 if n<0 else 100)
        if n>=0:self.progress.setValue(n)
    def end_job(self):
        old=self.job;self.job=None
        if old:old.deleteLater()
        self.job_host.hide();self.import_button.setEnabled(True);self.open_button.setEnabled(True);self.cancel_button.setEnabled(True);self.refresh_library()
        if self.quit_after:QTimer.singleShot(0,self.close)
    def task_start(self,fn,success,message):
        if self.busy():self.status_message('请先等待当前任务完成');return
        self.show_job(-1,message);self.import_button.setEnabled(False);self.open_button.setEnabled(False)
        self.task=TaskThread(fn,self);self.task.progress.connect(self.show_job);self.task.result.connect(lambda result:self.guarded(lambda:success(result)))
        self.task.error.connect(self.status_message);self.task.finished.connect(self.task_done);self.task.start()
    def task_done(self):
        task=self.task;self.task=None
        if task:task.deleteLater()
        self.end_job()
    def cancel_task(self):
        self.cancel_button.setEnabled(False)
        if self.job:self.job.cancel()
        if self.task:self.task.cancelled.set();self.show_job(-1,'正在取消…')
    def import_audio(self,source=''):
        if self.busy():self.status_message('请等待当前任务完成，或先取消');return
        dialog=ImportDialog(source if isinstance(source,str) else '',self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        def start():
            if self.dirty:self.save_current()
            self.job=InferenceJob(self.library,dialog.source,dialog.config,self)
            self.job.progress.connect(self.show_job);self.job.result.connect(lambda p:self.guarded(lambda:self.open_project(p)))
            self.job.error.connect(self.status_message);self.job.finished.connect(self.end_job)
            self.show_job(-1,'正在启动识别引擎…');self.import_button.setEnabled(False);self.open_button.setEnabled(False)
        self.guarded(start)
    def open_file(self,file=''):
        if self.busy():self.status_message('请先等待当前任务完成');return
        if not isinstance(file,str) or not file:file,_=QFileDialog.getOpenFileName(self,'打开完整项目或旧版项目','','BandTab 项目 (*.bandtab);;旧版项目 (project.json)')
        if not file:return
        def load(update,check):return self.library.import_legacy(file) if Path(file).suffix.lower()=='.json' else self.library.import_package(file,check)
        self.task_start(load,self.open_project,'正在导入项目与音频…')
    def open_demo(self):
        if self.busy():self.status_message('请先等待当前任务完成');return
        def create(update,check):
            folder=self.library.create_folder();p=demo.create(folder);self.library.save(p);return p
        self.task_start(create,self.open_project,'正在准备原创练习曲…')
    def share(self):
        if not self.project or self.busy():return
        self.save_action()
        if self.dirty:return
        file,_=QFileDialog.getSaveFileName(self,'分享完整项目',self.project['title']+'.bandtab','BandTab 完整项目 (*.bandtab)')
        if not file:return
        if not file.lower().endswith('.bandtab'):file+='.bandtab'
        p=copy.deepcopy(self.project)
        self.task_start(lambda update,check:self.library.export_package(p,file,check),lambda _:self.status_message('已打包谱子与音频，可发给其他 BandTab 用户：'+file),'正在打包完整音频和谱子…')
    def export_score(self,fmt):
        if not self.project:return
        self.save_action()
        if self.dirty:return
        suffix={'midi':'mid','musicxml':'musicxml','txt':'txt'}[fmt]
        file,_=QFileDialog.getSaveFileName(self,'导出谱子',self.project['title']+'.'+suffix,f'{suffix.upper()} (*.{suffix})')
        if file:
            if not file.lower().endswith('.'+suffix):file+='.'+suffix
            def write():
                Path(file).write_bytes({'midi':export.midi,'musicxml':export.musicxml,'txt':export.text_tab}[fmt](self.project))
                self.status_message('谱子已导出：'+file)
            self.guarded(write)
    def engine_dialog(self):
        caps=capabilities();d=QDialog(self);d.setWindowTitle('引擎与离线模型');d.setMinimumWidth(500);layout=QVBoxLayout(d)
        status='已缓存并校验' if valid_model(model_path()) else '尚未准备；可从安装包恢复或下载'
        text=label(f"音频解码：{'就绪' if caps['decoder'] else '仅 WAV'}\nAI 音符识别：{'已安装' if caps['basic_pitch'] else '未安装'}\n六轨分离引擎：{'已安装' if caps['demucs'] else '未安装'}\n分轨模型：{status}\n\n模型位置：{model_path()}\n\n完整版包含运行库。模型准备后可离线识别，不需要安装 Python。")
        text.setWordWrap(True);layout.addWidget(text)
        prepare=button('准备 / 校验离线模型',primary=True);prepare.setEnabled(not self.busy() and caps['demucs'])
        prepare.clicked.connect(lambda:(d.accept(),self.task_start(lambda update,check:ensure_model(update,check),lambda _:self.status_message('离线模型已就绪'),'正在准备离线模型…')));layout.addWidget(prepare)
        layout.addWidget(button('关闭',d.accept));d.exec()
    def help_dialog(self):
        text='1. 导入音乐：完整混音选「完整乐队」，已有分轨选「单乐器多音」。\n2. 先核对调弦、变调夹、BPM 和第一小节重拍。\n3. 点击谱面跳转；点击音符修改；音符清单支持键盘选择和回车编辑。\n4. A/B 循环、慢放、M 静音、S 独奏方便逐句练习。\n5.「分享完整项目」包含音频，另一台电脑可以直接打开。\n\n识别结果需复核：复杂失真、叠录、奏法和鼓点不能完全自动还原。六分轨不能保证分开主音/节奏吉他。\nMIDI 保留真实时值，MusicXML 按十六分网格；弱起、三连音、特殊奏法需后期整理。\n\nCtrl+O 导入音频 · Ctrl+S 保存 · Ctrl+Z 撤销。\n项目数据独立保存在用户目录，更新软件不会覆盖曲库。'
        if self.project:text+='\n\n当前项目提示：\n'+'\n'.join(self.project.get('warnings',[]))
        QMessageBox.information(self,'使用说明',text)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and not self.busy():event.acceptProposedAction()
    def dropEvent(self,event):
        files=[u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if files:
            file=files[0]
            if Path(file).suffix.lower() in ('.bandtab','.json'):self.open_file(file)
            else:self.import_audio(file)
            event.acceptProposedAction()
    def closeEvent(self,event):
        if self.busy():
            if not self.quit_after:
                answer=QMessageBox.question(self,'任务仍在运行','取消任务后退出？当前处理片段结束前窗口会保持打开。')
                if answer==QMessageBox.StandardButton.Yes:self.quit_after=True;self.cancel_task()
            event.ignore();return
        try:
            if self.dirty:self.save_current()
        except Exception as e:self.error(e);event.ignore();return
        self.transport.shutdown();event.accept()
