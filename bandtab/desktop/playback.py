"""Local-file playback with shared transport, pitch compensation and stem mixing."""
from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices


class Transport(QObject):
    position = Signal(float)
    playing = Signal(bool)
    error = Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.master=None;self.players=[];self.outputs=[];self.tracks=[];self.mixer={}
        self.stem_mode=False;self.loop=None;self.rate=1.;self.duration=0
        self.timer=QTimer(self);self.timer.setInterval(40);self.timer.timeout.connect(self.tick);self.timer.start()
        self.sync_ticks=0
    def new_player(self):
        p=QMediaPlayer(self);out=QAudioOutput(self);p.setAudioOutput(out)
        p.errorOccurred.connect(lambda code,msg:self.fail(msg))
        p.setPlaybackRate(self.rate)
        if hasattr(p,'setPitchCompensation'):p.setPitchCompensation(True)
        self.players.append(p);self.outputs.append(out);return p
    def load(self,project,library):
        self.stop()
        for p in self.players:p.setSource(QUrl());p.deleteLater()
        for out in self.outputs:out.deleteLater()
        self.players=[];self.outputs=[];self.tracks=project['tracks'];self.stem_mode=False;self.loop=None;self.duration=project['duration']
        self.mixer={t['id']:dict(mute=False,solo=False,volume=.85) for t in self.tracks}
        self.master=self.new_player();self.master.setSource(QUrl.fromLocalFile(str(library.asset(project))))
        self.master.playbackStateChanged.connect(lambda s:self.playing.emit(s==QMediaPlayer.PlaybackState.PlayingState))
        self.master.mediaStatusChanged.connect(self.status)
        for t in self.tracks:self.new_player().setSource(QUrl.fromLocalFile(str(library.asset(project,t))))
        self.volumes()
        if not QMediaDevices.audioOutputs():
            self.error.emit('未检测到音频输出设备。可以转写和编辑，请在系统声音设置中连接扬声器或耳机。')
    def shutdown(self):
        """Release decoder file handles before Windows closes/deletes a project."""
        self.timer.stop()
        self.stop()
        for player in self.players:
            player.setSource(QUrl())
            player.deleteLater()
        for output in self.outputs:output.deleteLater()
        self.players=[];self.outputs=[];self.master=None
    def status(self,status):
        if status==QMediaPlayer.MediaStatus.EndOfMedia:
            if self.loop:self.seek(self.loop[0]);self.play()
            else:self.stop()
    def fail(self,message):
        self.stop();self.error.emit('音频播放失败：'+message)
    def is_playing(self):return self.master is not None and self.master.playbackState()==QMediaPlayer.PlaybackState.PlayingState
    def seconds(self):return self.master.position()/1000 if self.master else 0.
    def play(self):
        if not self.master:return
        if self.master.position()>=int(self.duration*1000)-50:self.seek(0)
        for p in self.players[1:]:
            p.setPosition(self.master.position())
            if self.stem_mode:p.play()
        self.master.play()
    def pause(self):
        for p in self.players:p.pause()
        self.playing.emit(False)
    def stop(self):
        for p in self.players:p.stop()
        self.playing.emit(False)
    def toggle(self):self.pause() if self.is_playing() else self.play()
    def seek(self,seconds):
        ms=int(max(0,min(self.duration,seconds))*1000)
        for p in self.players:p.setPosition(ms)
        self.position.emit(ms/1000)
    def set_rate(self,rate):
        self.rate=rate
        for p in self.players:p.setPlaybackRate(rate)
    def set_stems(self,enabled):
        self.stem_mode=enabled;self.volumes()
        if not self.master:return
        for p in self.players[1:]:
            if enabled:
                p.setPosition(self.master.position())
                if self.is_playing():p.play()
            else:p.pause()
    def volumes(self):
        if not self.outputs:return
        self.outputs[0].setVolume(0 if self.stem_mode else 1)
        solo=any(v['solo'] for v in self.mixer.values())
        for t,out in zip(self.tracks,self.outputs[1:]):
            m=self.mixer[t['id']]
            out.setVolume(m['volume'] if self.stem_mode and not m['mute'] and (not solo or m['solo']) else 0)
    def tick(self):
        if not self.master:return
        t=self.seconds()
        if self.loop and self.is_playing() and t>=self.loop[1]:self.seek(self.loop[0]);t=self.loop[0]
        self.position.emit(t);self.sync_ticks+=1
        if self.stem_mode and self.is_playing() and self.sync_ticks%15==0:
            for p in self.players[1:]:
                if abs(p.position()-self.master.position())>120:p.setPosition(self.master.position())
