"""Native painted waveform and tablature. Draw only the visible time range."""
from PySide6.QtCore import Qt, Signal, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget
from bandtab.score import note_name

INK = QColor('#e8efdf')
MUTED = QColor('#94a08b')
LIME = QColor('#c3ee87')
AMBER = QColor('#efbc78')


def clock(seconds):
    seconds = max(0,seconds)
    return f'{int(seconds//60)}:{seconds%60:04.1f}'


class Waveform(QWidget):
    seek = Signal(float)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60);self.setMaximumHeight(80)
        self.setAccessibleName('音频波形，点击跳转')
        self.project = None;self.position = 0;self.loop = (None,None)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def paintEvent(self,event):
        q = QPainter(self);q.fillRect(self.rect(),QColor('#192016'))
        if not self.project:return
        d = self.project['duration'];w = self.width();h = self.height()
        a,b = self.loop
        if a is not None and b is not None:q.fillRect(QRectF(a/d*w,0,(b-a)/d*w,h),QColor('#303e23'))
        peaks = self.project.get('waveform',[])
        for x in range(0,w,3):
            v = peaks[min(len(peaks)-1,int(x/max(1,w)*len(peaks)))] if peaks else 0
            q.setPen(QPen(LIME if x/w*d<=self.position else QColor('#556746'),2))
            height = max(2,min(h-8,v*h*1.5))
            q.drawLine(x,int((h-height)/2),x,int((h+height)/2))
        q.setPen(QPen(LIME,2));q.drawLine(int(self.position/d*w),0,int(self.position/d*w),h)
    def mousePressEvent(self,e):
        if self.project:self.seek.emit(e.position().x()/max(1,self.width())*self.project['duration'])


class ScoreCanvas(QWidget):
    seek = Signal(float)
    edit = Signal(str,str)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setAccessibleName('动态乐队谱；音符清单提供键盘编辑入口')
        self.project=None;self.position=0;self.scale=95;self.track_id='all';self.review_only=False;self.hits=[]
        self.setMinimumSize(700,300)
    def tracks(self):
        return [t for t in self.project['tracks'] if self.track_id in ('all',t['id'])] if self.project else []
    def set_project(self,p):
        self.project=p;self.relayout()
    def relayout(self):
        h=64+sum(175 if t.get('tuning') else 140 for t in self.tracks())
        self.resize(max(700,int(self.project['duration']*self.scale+150) if self.project else 700),max(250,h))
        self.update()
    def x(self,t):return 80+t*self.scale
    def paintEvent(self,event):
        q=QPainter(self);q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.fillRect(event.rect(),QColor('#191e16'));self.hits=[]
        if not self.project:
            q.setPen(MUTED);q.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'导入音乐或打开演示，开始跟谱排练');return
        p=self.project;left,right=event.rect().left()-50,event.rect().right()+50
        q.setFont(QFont('Sans Serif',9))
        for i,t in enumerate(p['beats']):
            x=self.x(t)
            if x<left or x>right or t>p['duration']:continue
            bar=i%p['meter']==0
            q.setPen(QPen(QColor('#48543c') if bar else QColor('#2b3424'),1))
            q.drawLine(int(x),28,int(x),self.height())
            if bar:q.setPen(MUTED);q.drawText(int(x+6),19,f'{i//p["meter"]+1:02d}')
        for c in p.get('chords',[]):
            if left<=self.x(c['start'])<=right:
                q.setPen(LIME);q.drawText(int(self.x(c['start'])+6),46,c['label'])
        top=64
        for track in self.tracks():
            tuning=track.get('tuning');drums=track['instrument']=='drums';height=175 if tuning else 140
            q.setPen(QColor('#303a28'));q.drawLine(event.rect().left(),top,event.rect().right(),top)
            # Labels stay visible when the timeline scrolls horizontally.
            label_x=max(8,event.rect().left()+8)
            q.fillRect(QRectF(label_x,top+5,65,height-12),QColor('#192016'))
            q.setPen(LIME);q.drawText(label_x+3,top+23,track['name'].split(' · ')[0][:7])
            labels=[note_name(v) for v in tuning] if tuning else ['HH','SN','BD'] if drums else ['高','中','低']
            def row_y(i):return top+48+i*(20 if tuning else 28)
            for i,label in enumerate(labels):
                y=row_y(i);q.setPen(QColor('#48533e'));q.drawLine(label_x+65,y,event.rect().right(),y)
                q.setPen(MUTED);q.drawText(label_x+12,y+4,label)
            for n in track['notes']:
                x=self.x(n['start'])
                if x<max(left,label_x+70) or x>right:continue
                if tuning:y=row_y(n['string']-1) if n.get('string') else top+height-11
                elif drums:y=row_y({42:0,38:1,36:2}.get(n['pitch'],2))
                else:y=top+48+int((1-max(0,min(1,(n['pitch']-36)/60)))*64)
                active=n['start']<=self.position<n['end'];color=AMBER if n.get('review') else LIME
                q.setOpacity(.25 if self.review_only and not n.get('review') else 1)
                label=str(n['fret']) if tuning and n.get('fret') is not None else '?' if tuning else '×' if drums else note_name(n['pitch'])
                q.setPen(QPen(color,2));q.drawLine(int(x),int(y),int(min(right,self.x(n['end']))),int(y))
                rect=QRectF(x-14,y-10,max(28,len(label)*8+6),20)
                q.setBrush(LIME if active else QColor('#473923') if n.get('review') else QColor('#2e4122'))
                q.setPen(QPen(color,1));q.drawRoundedRect(rect,4,4)
                q.setPen(QColor('#14200d') if active else color);q.drawText(rect,Qt.AlignmentFlag.AlignCenter,label)
                self.hits.append((rect,track['id'],n['id']))
            q.setOpacity(1)
            if not track['notes']:q.setPen(MUTED);q.drawText(label_x+100,top+75,'仅试听伴奏' if track['instrument']=='other' else '未检测到音符，可手动添加')
            top+=height
        q.setPen(QPen(LIME,2));x=int(self.x(self.position));q.drawLine(x,0,x,self.height())
    def mousePressEvent(self,e):
        for rect,track,note in reversed(self.hits):
            if rect.contains(e.position()):self.edit.emit(track,note);return
        if self.project:self.seek.emit(max(0,min(self.project['duration'],(e.position().x()-80)/self.scale)))
