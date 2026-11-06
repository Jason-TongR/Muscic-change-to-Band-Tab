"""A deterministic, original 8-bar practice riff. Score is authored, not inferred."""
import numpy as np
from .audio import write_wav, waveform
from .score import TUNINGS, prepare


def create(directory):
    sr, bpm, duration = 22050, 108, 18.1
    beat = 60/bpm
    rng = np.random.default_rng(7)
    tracks = []
    mix = np.zeros(int(duration*sr))
    for instrument, label in [('guitar', '吉他'), ('bass', '贝斯'), ('drums', '鼓组')]:
        notes = []
        for bar in range(8):
            root = [40, 43, 45, 40][bar % 4]
            pattern = [0, 7, 12, 7, 3, 7, 12, 15]
            for j in range(8 if instrument != 'bass' else 4):
                start = (bar*4+j*(1 if instrument == 'bass' else .5))*beat
                if instrument == 'drums':
                    pitches = [42]+([36] if j in (0, 4) else [38] if j in (2, 6) else [])
                else:
                    pitches = [root-12 if instrument == 'bass' else root+pattern[j]]
                for pitch in pitches:
                    notes.append(dict(id=f'{instrument}-{len(notes)}', start=start, end=start+(.12 if instrument == 'drums' else beat*.42), pitch=pitch,
                                      velocity=95, confidence=1., review=False))
        wave = np.zeros_like(mix)
        for n in notes:
            a = int(n['start']*sr); length = min(len(wave)-a, int((n['end']-n['start'])*sr))
            t = np.arange(length)/sr
            freq = 440*2**((n['pitch']-69)/12)
            if instrument == 'drums':
                sound = np.sin(2*np.pi*(75*t-90*t*t))*np.exp(-t*28) if n['pitch'] == 36 else rng.normal(0, .3, length)*np.exp(-t*(40 if n['pitch'] == 42 else 23))
            else:
                sound = (np.sin(2*np.pi*freq*t)+.28*np.sin(4*np.pi*freq*t)+.12*np.sin(6*np.pi*freq*t))*np.exp(-t*7)
            wave[a:a+length] += sound*.22*np.minimum(1, t*800)
        write_wav(directory/f'{instrument}.wav', wave, sr)
        mix += wave
        tracks.append(dict(id=instrument, instrument=instrument, name=label,
                           audio=f'{instrument}.wav', notes=notes, capo=0,
                           tuning=TUNINGS['standard'] if instrument == 'guitar' else TUNINGS['bass'] if instrument == 'bass' else None, method='authored-demo'))
    write_wav(directory/'audio.wav', mix, sr)
    return prepare(dict(version=1, id=directory.name, title='车库练习曲 · 功能演示', duration=duration, bpm=bpm,
                        meter=4, offset=0, beats=[i*beat for i in range(34)], beat_source='authored', mode='demo',
                        audio='audio.wav', tracks=tracks, waveform=waveform(mix),
                        chords=[dict(start=i*4*beat, end=(i+1)*4*beat, label=['Em', 'Gm', 'Am', 'Em'][i%4], confidence=1) for i in range(8)],
                        warnings=['这是内置原创合成音频与预先编写的谱子，用于体验播放、循环和编辑；不代表自动转写准确度。']))
