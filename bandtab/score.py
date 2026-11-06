"""Score validation, beat coordinates and physically constrained tab fingering."""
import bisect
import copy
import math

TUNINGS = {"standard": [64, 59, 55, 50, 45, 40], "drop_d": [64, 59, 55, 50, 45, 38],
           "half_down": [63, 58, 54, 49, 44, 39], "bass": [43, 38, 33, 28]}
NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def note_name(pitch):
    return NAMES[pitch % 12] + str(pitch // 12 - 1)


def finite(value, low, high, label):
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} 必须在 {low}–{high} 之间')
    return value


def options(raw=None):
    raw = raw or {}
    mode = raw.get('mode', 'preview')
    if mode not in ('preview', 'instrument', 'band'):
        raise ValueError('未知识别模式')
    tuning = raw.get('tuning', 'standard')
    if tuning not in ('standard', 'drop_d', 'half_down'):
        raise ValueError('未知调弦')
    instrument = raw.get('instrument', 'guitar')
    if instrument not in ('guitar', 'bass', 'piano', 'vocals'):
        raise ValueError('未知乐器')
    bpm = finite(raw.get('bpm', 0), 0, 300, 'BPM')
    if bpm != 0 and bpm < 30:
        raise ValueError('BPM 应为 0（自动）或 30–300')
    return dict(mode=mode, tuning=tuning, instrument=instrument,
                capo=int(finite(raw.get('capo', 0), 0, 12, '变调夹')),
                bpm=bpm,
                offset=finite(raw.get('offset', 0), 0, 3600, '首拍时间'),
                meter=int(finite(raw.get('meter', 4), 2, 7, '每小节拍数')),
                sensitivity=finite(raw.get('sensitivity', .5), .15, .85, '识别门限'),
                device='cuda' if raw.get('device') == 'cuda' else 'cpu')


def seconds_to_beats(seconds, beats, bpm):
    if len(beats) < 2:
        return seconds * bpm / 60
    i = max(0, min(len(beats) - 2, bisect.bisect_right(beats, seconds) - 1))
    return i + (seconds - beats[i]) / max(.001, beats[i+1] - beats[i])


def beat_to_seconds(beat, beats, bpm):
    if len(beats) < 2:
        return beat * 60 / bpm
    i = max(0, min(len(beats) - 2, math.floor(beat)))
    return beats[i] + (beat-i) * (beats[i+1]-beats[i])


def assign_fingering(notes, tuning, capo=0, max_fret=24):
    """Beam search: chord uniqueness, held strings, hand span, and hand movement.

    Unplayable pitches remain in the score, with string/fret null and review=True.
    No octave substitution is performed. Frets are relative to capo.
    """
    notes.sort(key=lambda n: (n['start'], n['pitch']))
    groups = []
    for note in notes:
        if not groups or note['start'] - groups[-1][0]['start'] > .035:
            groups.append([])
        groups[-1].append(note)
    # state: accumulated cost, hand position, active (string, end), assignment path
    beam = [(0., 5., (), None, 0)]
    for group in groups:
        next_states = []
        for cost, hand, held, path, missed in beam:
            occupied = {s: end for s, end in held if end > group[0]['start'] + .03}
            partial = [(0., [], set(), [])]
            for n in group:
                choices = [(i+1, n['pitch'] - p - capo) for i, p in enumerate(tuning)
                           if 0 <= n['pitch'] - p - capo <= max_fret]
                candidates = []
                for c, assigned, used, frets in partial:
                    available = [(s, f) for s, f in choices if s not in used and s not in occupied]
                    for s, f in available:
                        nf = frets + ([f] if f else [])
                        span = max(nf)-min(nf) if nf else 0
                        penalty = abs(f-hand)*.12 + max(0, span-4)*8 + f*.025
                        candidates.append((c+penalty, assigned+[(s, f)], used | {s}, nf))
                    # Keep a flagged note if all strings are occupied.
                    if not available:
                        candidates.append((c+80, assigned+[(None, None)], used, frets))
                partial = sorted(candidates, key=lambda x: (sum(s is None for s, f in x[1]), x[0]))[:24]
            for c, assignment, used, frets in partial:
                new_hand = sum(frets)/len(frets) if frets else hand
                active = tuple(occupied.items()) + tuple((s, n['end']) for n, (s, f) in zip(group, assignment) if s)
                next_states.append((cost+c+abs(new_hand-hand)*.4, new_hand, active, (path, assignment), missed+sum(s is None for s, f in assignment)))
        beam = sorted(next_states, key=lambda x: (x[4], x[0]))[:16]
    if beam:
        path = beam[0][3]
        assignments = []
        while path is not None:
            path, assigned = path
            assignments.append(assigned)
        for group, assigned in zip(groups, reversed(assignments)):
            fretted = [f for s, f in assigned if f]
            wide = bool(fretted and max(fretted)-min(fretted) > 5)
            for n, (s, f) in zip(group, assigned):
                n.update(string=s, fret=f)
                if s is None or wide:
                    n['review'] = True
    return notes


def prepare(project, refinger=True):
    bpm, beats = project['bpm'], project['beats']
    for track in project['tracks']:
        for n in track['notes']:
            n['beat'] = round(max(0, seconds_to_beats(n['start'], beats, bpm))*4)/4
            end = round(max(0, seconds_to_beats(n['end'], beats, bpm))*4)/4
            n['length'] = max(.25, end-n['beat'])
            n['review'] = bool(n.get('review')) or (refinger and n['confidence'] < .6)
        if refinger and track.get('tuning'):
            assign_fingering(track['notes'], track['tuning'], track.get('capo', 0))
    return project


def validate_project(raw, original):
    """Only accept editable musical fields; never accept file paths from the client."""
    p = copy.deepcopy(original)
    p['title'] = str(raw.get('title', p['title']))[:160]
    p['bpm'] = finite(raw.get('bpm', p['bpm']), 30, 300, 'BPM')
    p['meter'] = int(finite(raw.get('meter', p['meter']), 2, 7, '拍号'))
    offset = finite(raw.get('offset', p.get('offset', 0)), 0, p['duration'], '首拍')
    if p['bpm'] != original['bpm'] or offset != original.get('offset', 0):
        # Negative beat anchors retain leading audio; the offset is the first bar downbeat.
        p['beats'] = [round(offset+i*60/p['bpm'], 6) for i in range(math.ceil(p['duration']*p['bpm']/60)+2)]
        p['beat_source'] = 'manual'
    p['offset'] = offset
    incoming = {t['id']: t for t in raw.get('tracks', [])}
    for track in p['tracks']:
        if track['id'] not in incoming:
            raise ValueError('谱子缺少声部')
        src = incoming[track['id']]
        if len(src.get('notes', [])) > 50000:
            raise ValueError('音符过多')
        clean = []
        ids = set()
        for n in src.get('notes', []):
            start = finite(n['start'], 0, p['duration'], '音符开始')
            end = finite(n['end'], start+.005, p['duration']+.1, '音符结束')
            pitch = int(finite(n['pitch'], 0, 127, '音高'))
            if track['instrument'] == 'drums' and pitch not in (36, 38, 42):
                raise ValueError('鼓点目前支持 MIDI 36（底鼓）、38（军鼓）、42（踩镲）')
            nid = str(n['id'])[:80]
            if nid in ids:
                raise ValueError('重复音符编号')
            ids.add(nid)
            item = dict(id=nid, start=start, end=end, pitch=pitch,
                        velocity=int(finite(n.get('velocity', 90), 1, 127, '力度')),
                        confidence=finite(n.get('confidence', .5), 0, 1, '识别分数'),
                        review=bool(n.get('review', False)))
            s, f = n.get('string'), n.get('fret')
            if track.get('tuning') and s is not None and f is not None:
                s = int(finite(s, 1, len(track['tuning']), '弦号'))
                f = int(finite(f, 0, 24, '品位'))
                if track['tuning'][s-1] + track.get('capo', 0) + f != pitch:
                    raise ValueError('品位与音高不一致')
                item.update(string=s, fret=f)
            else:
                item.update(string=None, fret=None)
            clean.append(item)
        track['notes'] = sorted(clean, key=lambda n: (n['start'], n['pitch']))
    return prepare(p, refinger=False)
