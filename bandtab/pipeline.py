"""Transcription pipeline, optional Demucs/Basic Pitch adapters, cancellable jobs."""
import importlib.util
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from . import audio
from .score import options, prepare, TUNINGS


class Cancelled(Exception):
    pass


def capabilities():
    has = lambda name: importlib.util.find_spec(name) is not None
    return dict(decoder=bool(audio.ffmpeg_path()), basic_pitch=has('basic_pitch'),
                demucs=has('demucs'), python=sys.version.split()[0],
                numpy=has('numpy'), scipy=has('scipy'))


def separate(source, directory, config, check):
    exe = audio.ffmpeg_path()
    env = os.environ.copy()
    env['TORCH_HOME'] = os.environ.get('BANDTAB_MODEL_HOME', str(directory.parent / 'models'))
    if exe:
        bindir = directory / 'bin'
        bindir.mkdir(exist_ok=True)
        link = bindir / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
        if not link.exists():
            try:
                link.symlink_to(exe)
            except OSError:
                import shutil
                shutil.copy2(exe, link)
        env['PATH'] = str(bindir.resolve()) + os.pathsep + env.get('PATH', '')
    from .runtime import worker_command, process_options
    prefix = worker_command('--demucs-worker') if getattr(sys, 'frozen', False) else [sys.executable, '-m', 'demucs']
    command = prefix + ['-n', 'htdemucs_6s', '--shifts', '2',
               '--overlap', '0.25', '--segment', '7', '-d', config['device'],
               '-o', str(directory / 'stems'), str(source)]
    with (directory/'separation.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=log, env=env, **process_options())
        try:
            while process.poll() is None:
                check()
                time.sleep(.4)
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            raise
    if process.returncode:
        raise RuntimeError('乐器分离失败。请查看该项目的 separation.log；首次运行需要联网下载模型。')
    folder = directory/'stems'/'htdemucs_6s'/source.stem
    return {name: folder/f'{name}.wav' for name in ('guitar', 'bass', 'drums', 'piano', 'vocals', 'other')}


def neural_notes(path, instrument, sensitivity, scratch, check):
    import basic_pitch
    from basic_pitch.inference import Model, predict
    import soundfile as sf
    from pathlib import Path
    # ONNX is explicit to avoid importing a second heavyweight inference runtime.
    model_path = Path(basic_pitch.__file__).parent/'saved_models'/'icassp_2022'/'nmp.onnx'
    model = Model(str(model_path))
    limits = dict(guitar=(28, 100), bass=(23, 67), piano=(21, 108), vocals=(40, 90))
    low, high = limits[instrument]
    result = []
    with sf.SoundFile(str(path)) as stream:
        sr, duration = stream.samplerate, len(stream)/stream.samplerate
        for begin in range(0, math.ceil(duration), 30):
            check()
            left, right = max(0, begin-1), min(duration, begin+31)
            stream.seek(int(left*sr))
            segment = stream.read(int((right-left)*sr), dtype='float32', always_2d=True)
            chunk = scratch/'inference.wav'
            sf.write(str(chunk), segment, sr)
            _, _, events = predict(str(chunk), model_or_model_path=model,
                                   onset_threshold=sensitivity, frame_threshold=max(.15, sensitivity-.2),
                                   minimum_note_length=85,
                                   minimum_frequency=440*2**((low-69)/12),
                                   maximum_frequency=440*2**((high-69)/12))
            for start, end, pitch, amplitude, *_ in events:
                start, end = float(start)+left, min(duration, float(end)+left)
                # Retain the central 30s of each overlapping window. Continue a
                # held note across the boundary only when the next window detects
                # its onset before the boundary (not a new repeated attack).
                central_end = min(begin+30, duration)
                if end <= begin or start >= central_end:
                    continue
                previous = next((n for n in reversed(result) if n['pitch'] == int(pitch)
                                 and abs(n['end']-begin) < .04), None)
                if start < begin-.05 and previous is not None:
                    previous['end'] = round(min(end, central_end), 4)
                    continue
                start, end = max(start, begin), min(end, central_end)
                if end > start+.02:
                    result.append(dict(start=round(start, 4), end=round(end, 4), pitch=int(pitch),
                                       velocity=max(1, min(127, int(float(amplitude)*127))),
                                       confidence=round(float(amplitude), 3), review=float(amplitude) < .6))
    return sorted(result, key=lambda n: n['start'])


def transcribe(source, directory, raw_config, update=lambda *args: None, check=lambda: None):
    config = options(raw_config)
    caps = capabilities()
    if config['mode'] != 'preview' and not caps['basic_pitch']:
        raise ValueError('尚未安装完整识别引擎。请运行 scripts/install_ai.sh；当前可使用「基础旋律」模式。')
    if config['mode'] == 'band' and not caps['demucs']:
        raise ValueError('尚未安装 Demucs。请运行 scripts/install_ai.sh。')
    update(5, '正在解码音频')
    target = directory/'audio.wav'
    duration = audio.decode(source, target)
    check()
    y, sr = audio.read_wav(target)
    if float(abs(y).max()) < .0001:
        raise ValueError('音频没有可识别的声音。')
    update(12, '正在分析节拍与和弦参考')
    bpm, beats, offset = audio.rhythm(y, sr, config['bpm'], config['offset'])
    beat_source = 'manual' if config['bpm'] else 'estimated_constant'
    if config['mode'] != 'preview' and not config['bpm']:
        import librosa
        tempo, detected = librosa.beat.beat_track(y=y, sr=sr, units='time', trim=False)
        if len(detected) >= 3:
            bpm = float(tempo.item())
            beats = [float(v) for v in detected]
            offset, beat_source = beats[0], 'detected_variable'
            # Extend the final beat so the full audio has a time coordinate.
            while beats[-1] < duration:
                beats.append(beats[-1]+60/bpm)
    warnings = ['拍号和第一小节重拍不能可靠自动判断；默认 4/4，请按听感校正。',
                '和弦仅为大/小三和弦参考；识别分数不是准确率。推弦、滑音、闷音等奏法尚不还原。']
    if config['mode'] == 'band':
        update(20, '正在分离六个声部；首次会下载模型，请耐心等待')
        if os.environ.get('BANDTAB_MODEL_HOME'):
            from .runtime import ensure_model
            ensure_model(lambda n, message: update(20+int(n*.05), message), check)
        sources = separate(target, directory, config, check)
        warnings += ['吉他轨可能混有多把吉他，不能保证主音/节奏吉他分开。',
                     '鼓谱是低/中/高频起音估计，仅提供底鼓、军鼓、踩镲参考；不能识别完整鼓组。']
    else:
        sources = {config['instrument']: target}
        if config['mode'] == 'preview':
            warnings.append('基础模式只估计单音旋律，不分离乐器，不适用于把整首混音直接还原为完整乐队谱。')
    tracks = []
    titles = dict(guitar='吉他', bass='贝斯', drums='鼓组 · 参考', piano='键盘', vocals='人声', other='其他伴奏')
    for index, (instrument, path) in enumerate(sources.items()):
        check()
        update(45+int(index/max(1, len(sources))*45), f'正在转写{titles[instrument]}')
        if instrument == 'other':
            notes = []
        elif instrument == 'drums':
            stem_y, stem_sr = audio.read_wav(path)
            notes = audio.drum_notes(stem_y, stem_sr)
        elif config['mode'] == 'preview':
            ranges = dict(guitar=(36, 88), bass=(23, 67), piano=(36, 96), vocals=(40, 90))
            notes = audio.melody(y, sr, *ranges[instrument], config['sensitivity'], check)
        else:
            notes = neural_notes(path, instrument, config['sensitivity'], directory, check)
        for i, n in enumerate(notes):
            n['id'] = f'{instrument}-{i}'
        tuning = TUNINGS[config['tuning']] if instrument == 'guitar' else TUNINGS['bass'] if instrument == 'bass' else None
        tracks.append(dict(id=instrument, name=titles[instrument]+(' · 单音参考' if config['mode'] == 'preview' else ''),
                           instrument=instrument, tuning=tuning, capo=config['capo'] if instrument == 'guitar' else 0,
                           audio=str(path.relative_to(directory)), notes=notes,
                           method='yin' if config['mode'] == 'preview' else 'spectral-onset' if instrument == 'drums' else 'basic-pitch' if instrument != 'other' else 'audio-only'))
    update(94, '正在编排指法与动态谱')
    project = dict(version=1, id=directory.name, title=source.stem, duration=duration,
                   bpm=round(bpm, 2), beats=beats, offset=offset, meter=config['meter'], beat_source=beat_source,
                   mode=config['mode'], audio='audio.wav', waveform=audio.waveform(y),
                   chords=audio.chords(y, sr, beats, config['meter']), tracks=tracks, warnings=warnings)
    prepare(project)
    check()
    return project
