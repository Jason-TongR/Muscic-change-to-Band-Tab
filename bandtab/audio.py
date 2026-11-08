"""Audio I/O and conservative signal-processing estimates; no fabricated stems."""
from pathlib import Path
import math
import os
import shutil
import subprocess
import wave
import numpy as np
from scipy import signal
from .score import NAMES

RATE = 22050


def ffmpeg_path():
    executable = shutil.which('ffmpeg')
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return None


def read_wav(path):
    from scipy.io import wavfile
    sr, data = wavfile.read(str(path))
    if data.dtype.kind in 'iu':
        if data.dtype == np.uint8:
            data = (data.astype(np.float32)-128)/128
        else:
            data = data.astype(np.float32)/max(abs(np.iinfo(data.dtype).min), np.iinfo(data.dtype).max)
    else:
        data = data.astype(np.float32)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != RATE:
        g = math.gcd(sr, RATE)
        data = signal.resample_poly(data, RATE//g, sr//g)
    return np.nan_to_num(data), RATE


def decode(source, dest, max_seconds=900):
    from .runtime import process_options
    exe = ffmpeg_path()
    if exe:
        # Decode at most max+1 seconds to bound memory and reject, never silently truncate.
        result = subprocess.run([exe, '-nostdin', '-v', 'error', '-y', '-i', str(source),
                                 '-t', str(max_seconds+1), '-vn', '-ac', '2', '-ar', '44100',
                                 '-c:a', 'pcm_s16le', str(dest)], capture_output=True, timeout=180,
                                **process_options())
        if result.returncode:
            raise ValueError('无法解码音频，请检查文件是否损坏。支持 WAV / MP3 / FLAC / M4A / OGG。')
    else:
        if source.suffix.lower() != '.wav':
            raise ValueError('缺少音频解码器。请运行安装脚本，或先使用 PCM WAV。')
        # Re-encode supported WAV to a browser-compatible PCM file.
        data, sr = read_wav(source)
        write_wav(dest, data, sr)
    with wave.open(str(dest)) as f:
        duration = f.getnframes()/f.getframerate()
    if duration > max_seconds:
        raise ValueError(f'单次支持最多 {max_seconds//60} 分钟，请先截取排练片段。')
    if duration < .3:
        raise ValueError('音频太短，至少需要 0.3 秒。')
    return duration


def write_wav(path, data, sr=RATE):
    from scipy.io import wavfile
    wavfile.write(str(path), sr, (np.clip(data, -.99, .99)*32767).astype(np.int16))


def frames(y, size=2048, hop=256):
    y = np.pad(y, (size//2, size//2))
    return np.lib.stride_tricks.sliding_window_view(y, size)[::hop]


def rhythm(y, sr, bpm_hint=0, offset=0):
    """Fallback spectral-flux autocorrelation tempo with explicit uncertainty."""
    hop = 256
    spec = abs(np.fft.rfft(frames(y, 1024, hop)*np.hanning(1024), axis=1))
    flux = np.maximum(0, np.diff(np.log1p(spec), axis=0)).mean(axis=1)
    flux = np.r_[0, flux]
    if bpm_hint:
        bpm = bpm_hint
    elif len(flux) > 8 and flux.max() > .001:
        ac = signal.fftconvolve(flux-flux.mean(), (flux-flux.mean())[::-1], mode='full')[len(flux)-1:]
        lo, hi = int(60*sr/hop/180), min(len(ac)-1, int(60*sr/hop/60))
        lag = lo + int(np.argmax(ac[lo:hi+1])) if hi >= lo else 0
        bpm = round(60*sr/hop/lag, 2) if lag else 120.
    else:
        bpm = 120.
    step = 60/bpm
    if not bpm_hint and flux.max() > .001:
        candidates = np.arange(0, step, hop/sr)
        scores = [np.interp(np.arange(t, len(y)/sr, step)*sr/hop, np.arange(len(flux)), flux).sum() for t in candidates]
        offset = float(candidates[np.argmax(scores)]) if len(candidates) else 0.
    beats = [round(offset+i*step, 6) for i in range(int(len(y)/sr/step)+2)]
    return float(bpm), beats, float(offset)


def melody(y, sr, low=40, high=88, sensitivity=.5, check=lambda: None):
    """FFT autocorrelation with CMNDF (YIN), amplitude gating and median stability.

    This is monophonic. Score is periodicity, not calibrated accuracy probability.
    """
    hop, size = 256, 2048
    fmin = 440*2**((low-69)/12)
    fmax = 440*2**((high-69)/12)
    lag_min, lag_max = max(2, int(sr/fmax)), min(size//2-1, math.ceil(sr/fmin))
    f = frames(y, size, hop)
    pitches, strengths, energies = [], [], []
    global_rms = float(np.sqrt(np.mean(y*y)))
    for k in range(0, len(f), 512):
        check()
        batch = f[k:k+512].astype(np.float64)
        batch -= batch.mean(axis=1, keepdims=True)
        # Fixed-window YIN difference function: compare first half with lagged copies.
        half = size//2
        left = batch[:, :half]
        ac = np.fft.irfft(np.conj(np.fft.rfft(left, n=4096, axis=1))*np.fft.rfft(batch, n=4096, axis=1), n=4096, axis=1)[:, :lag_max+1]
        squares = np.c_[np.zeros(len(batch)), np.cumsum(batch*batch, axis=1)]
        moving = squares[:, half:half+lag_max+1]-squares[:, :lag_max+1]
        diff = np.maximum(0, (left*left).sum(axis=1)[:, None]+moving-2*ac)
        cmnd = np.ones_like(diff)
        cmnd[:, 1:] = diff[:, 1:]*np.arange(1, lag_max+1)/np.maximum(1e-12, np.cumsum(diff[:, 1:], axis=1))
        rms = np.sqrt((batch*batch).mean(axis=1))
        for row, energy in zip(cmnd, rms):
            peaks, _ = signal.find_peaks(-row[lag_min:lag_max])
            candidates = peaks+lag_min
            good = candidates[row[candidates] < .22]
            lag = int(good[0]) if len(good) else lag_min+int(np.argmin(row[lag_min:lag_max]))
            quality = max(0., 1-float(row[lag]))
            shift = .5*(row[lag-1]-row[lag+1])/(row[lag-1]-2*row[lag]+row[lag+1]+1e-12) if lag < lag_max else 0
            pitch = round(69+12*math.log2(sr/(lag+float(np.clip(shift, -.5, .5)))/440))
            valid = energy > max(.003, global_rms*.12) and quality > max(.65, sensitivity) and low <= pitch <= high
            pitches.append(pitch if valid else -1)
            strengths.append(quality)
            energies.append(float(energy))
    pitches = np.asarray(pitches)
    if len(pitches) >= 3:
        pitches = signal.medfilt(pitches, 3).astype(int)
    notes = []
    begin = 0
    for i in range(1, len(pitches)+1):
        if i == len(pitches) or pitches[i] != pitches[begin]:
            start, end = max(0, (begin*hop-sr*.015)/sr), min(len(y)/sr, (i*hop-sr*.015)/sr)
            if pitches[begin] >= 0 and end-start >= .075:
                confidence = float(np.mean(strengths[begin:i]))
                velocity = int(np.clip(60+35*np.mean(energies[begin:i])/max(.01, global_rms), 30, 120))
                notes.append(dict(start=round(start, 4), end=round(end, 4), pitch=int(pitches[begin]),
                                  velocity=velocity, confidence=round(confidence, 3), review=True))
            begin = i
    return notes


def drum_notes(y, sr):
    """Three independent frequency-band onset lanes, deliberately labelled heuristic."""
    hop, size = 128, 1024
    spec = abs(np.fft.rfft(frames(y, size, hop)*np.hanning(size), axis=1))
    freq = np.fft.rfftfreq(size, 1/sr)
    notes = []
    for pitch, lo, hi in [(36, 35, 170), (38, 180, 2300), (42, 4500, 10000)]:
        energy = np.log1p(spec[:, (freq >= lo) & (freq < hi)].mean(axis=1))
        flux = np.maximum(0, np.diff(energy, prepend=energy[0]))
        if flux.max() < 1e-5:
            continue
        peaks, _ = signal.find_peaks(flux, height=max(.018, flux.max()*.18),
                                    prominence=flux.max()*.1, distance=int(.075*sr/hop))
        for i in peaks:
            start = max(0, i*hop/sr-.015)
            if start+.02 >= len(y)/sr:
                continue
            notes.append(dict(start=start, end=min(start+.08, len(y)/sr), pitch=pitch,
                              velocity=int(np.clip(flux[i]/flux.max()*110, 40, 120)), confidence=.4, review=True))
    return sorted(notes, key=lambda n: n['start'])


def chords(y, sr, beats, meter):
    # Harmonic pitch-class energy, major/minor templates. Intentionally only suggestions.
    size, hop = 4096, 1024
    spec = abs(np.fft.rfft(frames(y, size, hop)*np.hanning(size), axis=1))
    freq = np.fft.rfftfreq(size, 1/sr)
    valid = (freq > 65) & (freq < 2100)
    midi = np.rint(69+12*np.log2(freq[valid]/440)).astype(int)
    chroma = np.zeros((len(spec), 12))
    for c in range(12):
        chroma[:, c] = (spec[:, valid][:, midi % 12 == c]**.7).sum(axis=1)
    templates, labels = [], []
    for root in range(12):
        for intervals, suffix in [([0, 4, 7], ''), ([0, 3, 7], 'm')]:
            t = np.zeros(12)
            t[[(root+i) % 12 for i in intervals]] = 1
            templates.append(t/np.linalg.norm(t)); labels.append(NAMES[root]+suffix)
    result = []
    for i in range(0, len(beats)-1, meter):
        start, end = beats[i], beats[min(i+meter, len(beats)-1)]
        a, b = max(0, int(start*sr/hop)), min(len(chroma), int(end*sr/hop))
        vector = chroma[a:b].mean(axis=0) if b > a else np.zeros(12)
        norm = np.linalg.norm(vector)
        scores = np.asarray(templates) @ (vector/max(norm, 1e-8))
        best = int(np.argmax(scores))
        result.append(dict(start=start, end=end, label=labels[best] if norm > 1e-4 else 'N.C.',
                           confidence=round(float(scores[best]), 3)))
    return result


def waveform(y, count=1000):
    return [round(float(np.max(np.abs(part))), 4) if len(part) else 0 for part in np.array_split(y, count)]
