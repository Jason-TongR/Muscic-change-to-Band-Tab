"""Native input dialogs with immediate musical validation."""
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLabel,QComboBox,QSpinBox,QDoubleSpinBox,
                              QDialogButtonBox,QLineEdit,QPushButton,QHBoxLayout,QFileDialog,QCheckBox)
from bandtab.pipeline import capabilities
from bandtab.score import options,note_name


def combo(items):
    c=QComboBox()
    for label,value in items:c.addItem(label,value)
    return c


def number(low,high,value,decimals=0):
    n=QDoubleSpinBox() if decimals else QSpinBox();n.setRange(low,high)
    if decimals:n.setDecimals(decimals);n.setSingleStep(.01)
    n.setValue(value);return n


class ImportDialog(QDialog):
    def __init__(self,source='',parent=None):
        super().__init__(parent);self.setWindowTitle('导入音乐');self.setMinimumWidth(530)
        layout=QVBoxLayout(self);heading=QLabel('从一段音乐开始');heading.setObjectName('dialogTitle');layout.addWidget(heading)
        row=QHBoxLayout();self.file=QLineEdit(source);self.file.setPlaceholderText('选择音频，或把文件拖进主窗口');row.addWidget(self.file)
        pick=QPushButton('选择文件…');pick.clicked.connect(self.choose);row.addWidget(pick);layout.addLayout(row)
        form=QFormLayout();layout.addLayout(form)
        self.mode=combo([('完整乐队 · 六轨分离 + AI 转谱','band'),('单乐器多音 · 已分离音轨','instrument'),('基础单音 · 不分轨','preview')])
        self.caps=capabilities()
        if not self.caps['basic_pitch'] or not self.caps['demucs']:self.mode.setCurrentIndex(2)
        self.instrument=combo([('吉他','guitar'),('贝斯','bass'),('键盘','piano'),('人声','vocals')])
        self.tuning=combo([('标准 E A D G B E','standard'),('Drop D','drop_d'),('降半音','half_down')])
        self.capo=number(0,12,0);self.bpm=number(0,300,0,2);self.bpm.setSpecialValueText('自动估计')
        self.meter=combo([(f'{n}/4',n) for n in (4,3,2,6,7)])
        self.sensitivity=number(.15,.85,.5,2)
        self.device=combo([('CPU（通用）','cpu'),('NVIDIA CUDA（需 GPU 版运行库）','cuda')])
        for label,widget in [('识别模式',self.mode),('目标乐器',self.instrument),('吉他调弦',self.tuning),('变调夹（品）',self.capo),('BPM',self.bpm),('拍号',self.meter),('音符门限',self.sensitivity),('设备',self.device)]:form.addRow(label,widget)
        self.hint=QLabel();self.hint.setWordWrap(True);self.hint.setObjectName('muted');layout.addWidget(self.hint)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setObjectName('error');layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('开始转写');buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.submit);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.mode.currentIndexChanged.connect(self.refresh);self.refresh()
    def choose(self):
        file,_=QFileDialog.getOpenFileName(self,'选择音频','','音频 (*.wav *.mp3 *.flac *.m4a *.ogg *.aac *.aiff *.opus)')
        if file:self.file.setText(file)
    def refresh(self):
        mode=self.mode.currentData();self.instrument.setEnabled(mode!='band')
        self.hint.setText('基础模式只估计单音旋律，不会还原完整乐队。' if mode=='preview' else 'AI 结果需复核。首次准备模型可能需要联网；CPU 处理整曲较慢，可取消任务。')
    def submit(self):
        from pathlib import Path
        try:
            source=Path(self.file.text()).expanduser()
            if not source.is_file():raise ValueError('请选择存在的音频文件')
            if source.stat().st_size>200*1024**2:raise ValueError('音频超过 200 MB，请先截取片段')
            mode=self.mode.currentData()
            if mode!='preview' and not self.caps['basic_pitch']:raise ValueError('此版本没有 AI 引擎，请使用完整桌面发行版')
            if mode=='band' and not self.caps['demucs']:raise ValueError('此版本没有六轨分离引擎')
            self.config=options(dict(mode=mode,instrument=self.instrument.currentData(),tuning=self.tuning.currentData(),
                                     capo=self.capo.value(),bpm=self.bpm.value(),meter=self.meter.currentData(),
                                     sensitivity=self.sensitivity.value(),device=self.device.currentData()))
            self.source=str(source.resolve());self.accept()
        except (ValueError,OSError) as e:self.error.setText(str(e))


class NoteDialog(QDialog):
    def __init__(self,track,note,duration,parent=None):
        super().__init__(parent);self.setWindowTitle('校正音符');self.setMinimumWidth(420)
        self.track=track;self.original=note;self.duration=duration
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.pitch=number(0,127,note['pitch']);self.start=number(0,duration,note['start'],3)
        self.end=number(0,duration,note['end'],3);self.velocity=number(1,127,note['velocity'])
        self.position=QComboBox();self.review=QCheckBox('仍需复核');self.review.setChecked(note.get('review',False))
        self.name=QLabel();self.error=QLabel();self.error.setObjectName('error');self.error.setWordWrap(True)
        for label,widget in [('声部',QLabel(track['name'])),('实际音高（MIDI）',self.pitch),('音名',self.name),('开始（秒）',self.start),('结束（秒）',self.end),('弦 / 品（相对变调夹）',self.position),('力度',self.velocity),('',self.review)]:form.addRow(label,widget)
        layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('应用修改');buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        self.delete=buttons.addButton('删除音符',QDialogButtonBox.ButtonRole.DestructiveRole);self.delete.clicked.connect(self.remove)
        buttons.accepted.connect(self.submit);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.deleted=False;self.pitch.valueChanged.connect(self.fill);self.fill()
        preferred=(note.get('string'),note.get('fret'))
        for i in range(self.position.count()):
            if self.position.itemData(i)==preferred:self.position.setCurrentIndex(i)
    def fill(self):
        pitch=self.pitch.value();self.name.setText(note_name(pitch))
        self.position.clear();self.position.addItem('不指定（无可用指法时保留音高）',None)
        for i,p in enumerate(self.track.get('tuning') or []):
            fret=pitch-p-self.track.get('capo',0)
            if 0<=fret<=24:self.position.addItem(f'{i+1} 弦 / {fret} 品',(i+1,fret))
        if self.position.count()>1:self.position.setCurrentIndex(1)
        self.position.setEnabled(bool(self.track.get('tuning')))
    def remove(self):self.deleted=True;self.accept()
    def submit(self):
        if self.end.value()<=self.start.value()+.005:self.error.setText('结束时间必须大于开始时间');return
        if self.track['instrument']=='drums' and self.pitch.value() not in (36,38,42):self.error.setText('鼓点支持：36 底鼓、38 军鼓、42 踩镲');return
        position=self.position.currentData() or (None,None)
        self.result_note=dict(self.original,pitch=self.pitch.value(),start=self.start.value(),end=self.end.value(),velocity=self.velocity.value(),
                              string=position[0],fret=position[1],review=self.review.isChecked() or bool(self.track.get('tuning') and not position[0]))
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self,p,parent=None):
        super().__init__(parent);self.setWindowTitle('项目与节拍校正');self.setMinimumWidth(440)
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.title=QLineEdit(p['title']);self.title.setMaxLength(160)
        self.bpm=number(30,300,p['bpm'],2);self.meter=number(2,7,p['meter']);self.offset=number(0,p['duration'],p.get('offset',0),3)
        for label,widget in [('曲名',self.title),('BPM',self.bpm),('每小节四分音符拍数',self.meter),('首小节重拍（秒）',self.offset)]:form.addRow(label,widget)
        hint=QLabel('修改 BPM 或首拍后使用恒定网格；音符真实时间不变。\n首拍前的弱起音目前归入第一小节。');hint.setWordWrap(True);layout.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
