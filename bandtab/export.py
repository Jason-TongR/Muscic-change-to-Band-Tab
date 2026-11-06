"""Portable MIDI, MusicXML (with TAB technical indications), and text exports."""
import math
import struct
import xml.etree.ElementTree as ET
from .score import seconds_to_beats, note_name


def vlq(number):
    number = max(0, int(number))
    result = [number & 127]
    while number >> 7:
        number >>= 7
        result.insert(0, 128 | (number & 127))
    return bytes(result)


def midi(project):
    # Absolute audio time is encoded at 120 BPM. This preserves performed timing,
    # including pickups and tempo changes, independently of notation quantization.
    ppq = 960
    parts = []
    tempo = b'\x00\xff\x51\x03\x07\xa1\x20\x00\xff\x2f\x00'
    parts.append(b'MTrk'+struct.pack('>I', len(tempo))+tempo)
    channels = iter([0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15])
    programs = dict(guitar=27, bass=33, piano=0, vocals=53, other=0)
    for track in project['tracks']:
        channel = 9 if track['instrument'] == 'drums' else next(channels)
        name = track['name'].encode('utf8')
        events = [(0, -2, b'\xff\x03'+vlq(len(name))+name)]
        if channel != 9:
            events.append((0, -1, bytes([0xc0+channel, programs[track['instrument']]])))
        for n in track['notes']:
            events += [(round(n['start']*2*ppq), 1, bytes([0x90+channel, n['pitch'], n['velocity']])),
                       (max(round(n['start']*2*ppq)+1, round(n['end']*2*ppq)), 0, bytes([0x80+channel, n['pitch'], 0]))]
        payload, last = bytearray(), 0
        for tick, _, msg in sorted(events, key=lambda e: (e[0], e[1])):
            payload.extend(vlq(tick-last)+msg); last = tick
        payload.extend(b'\x00\xff\x2f\x00')
        parts.append(b'MTrk'+struct.pack('>I', len(payload))+payload)
    return b'MThd'+struct.pack('>IHHH', 6, 1, len(parts), ppq)+b''.join(parts)


def element(parent, tag, text=None, **attrs):
    e = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})
    if text is not None:
        e.text = str(text)
    return e


def musicxml(project):
    root = ET.Element('score-partwise', version='4.0')
    element(element(root, 'work'), 'work-title', project['title'])
    element(element(root, 'identification'), 'creator', 'BandTab Studio · 自动转写，请复核', type='software')
    parts = element(root, 'part-list')
    for index, track in enumerate(project['tracks']):
        sp = element(parts, 'score-part', id=f'P{index+1}')
        element(sp, 'part-name', track['name'])
        if track['instrument'] == 'drums':
            for pitch, label in [(36, 'Kick'), (38, 'Snare'), (42, 'Hi-hat')]:
                sid = f'P{index+1}-I{pitch}'
                element(element(sp, 'score-instrument', id=sid), 'instrument-name', label)
                mi = element(sp, 'midi-instrument', id=sid)
                element(mi, 'midi-channel', 10); element(mi, 'midi-unpitched', pitch+1)
        part = element(root, 'part', id=f'P{index+1}')
        # Allocate overlapping notes to independent voices. Each voice fills every bar.
        voices = []
        for n in sorted(track['notes'], key=lambda n: (n['beat'], n['pitch'])):
            start, end = round(n['beat']*4), round((n['beat']+n['length'])*4)
            voice = next((v for v in voices if v[-1][1] <= start), None)
            if voice is None:
                voice = []; voices.append(voice)
            voice.append((start, end, n))
        if not voices:
            voices = [[]]
        barlen = project['meter']*4
        last = max([end for v in voices for _, end, _ in v] + [barlen, math.ceil(max(0, seconds_to_beats(project['duration'], project['beats'], project['bpm']))*4)])
        for bar in range(math.ceil(last/barlen)):
            measure = element(part, 'measure', number=bar+1)
            if bar == 0:
                attrs = element(measure, 'attributes'); element(attrs, 'divisions', 4)
                time = element(attrs, 'time'); element(time, 'beats', project['meter']); element(time, 'beat-type', 4)
                clef = element(attrs, 'clef')
                element(clef, 'sign', 'percussion' if track['instrument'] == 'drums' else 'TAB' if track.get('tuning') else 'G')
                if track.get('tuning'):
                    element(clef, 'line', 5)
                    details = element(attrs, 'staff-details'); element(details, 'staff-lines', len(track['tuning']))
                    for line, pitch in enumerate(reversed(track['tuning']), 1):
                        tune = element(details, 'staff-tuning', line=str(line))
                        name = note_name(pitch)
                        element(tune, 'tuning-step', name[0])
                        if '#' in name: element(tune, 'tuning-alter', 1)
                        element(tune, 'tuning-octave', pitch//12-1)
                    if track.get('capo'): element(details, 'capo', track['capo'])
                elif track['instrument'] != 'drums': element(clef, 'line', 2)
                direction = element(measure, 'direction')
                element(element(direction, 'direction-type'), 'words', '量化至十六分音符；原始时值见 MIDI')
                element(direction, 'sound', tempo=str(project['bpm']))
            a, b = bar*barlen, (bar+1)*barlen
            for vi, voice in enumerate(voices, 1):
                if vi > 1: element(element(measure, 'backup'), 'duration', barlen)
                cursor = a
                for start, end, n in voice:
                    if start >= b or end <= a: continue
                    ns, ne = max(a, start), min(b, end)
                    if ns > cursor:
                        rest = element(measure, 'note'); element(rest, 'rest'); element(rest, 'duration', ns-cursor); element(rest, 'voice', vi)
                    note = element(measure, 'note')
                    if track['instrument'] == 'drums':
                        unpitched = element(note, 'unpitched')
                        step, octave = {36: ('F', 4), 38: ('C', 5), 42: ('G', 5)}.get(n['pitch'], ('C', 5))
                        element(unpitched, 'display-step', step); element(unpitched, 'display-octave', octave)
                    else:
                        pitch = element(note, 'pitch'); name = note_name(n['pitch'])
                        element(pitch, 'step', name[0])
                        if '#' in name: element(pitch, 'alter', 1)
                        element(pitch, 'octave', n['pitch']//12-1)
                    element(note, 'duration', ne-ns)
                    if start < a: element(note, 'tie', type='stop')
                    if end > b: element(note, 'tie', type='start')
                    if track['instrument'] == 'drums' and n['pitch'] in (36, 38, 42):
                        element(note, 'instrument', id=f'P{index+1}-I{n["pitch"]}')
                    element(note, 'voice', vi)
                    notation = element(note, 'notations')
                    if start < a: element(notation, 'tied', type='stop')
                    if end > b: element(notation, 'tied', type='start')
                    if n.get('string'):
                        technical = element(notation, 'technical')
                        element(technical, 'string', n['string']); element(technical, 'fret', n['fret'])
                    cursor = ne
                if cursor < b:
                    rest = element(measure, 'note'); element(rest, 'rest'); element(rest, 'duration', b-cursor); element(rest, 'voice', vi)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def text_tab(project):
    lines = [project['title'], f"{project['bpm']} BPM | {project['meter']}/4 | 十六分网格；? = 需要复核", '']
    for track in project['tracks']:
        lines.append(f"[{track['name']}]")
        if not track.get('tuning'):
            for n in track['notes']:
                lines.append(f"{n['start']:8.3f}s  {note_name(n['pitch']):4}  {n['end']-n['start']:.3f}s")
            continue
        bars = max([int(n['beat']//project['meter'])+1 for n in track['notes']] or [1])
        for bar in range(bars):
            lines.append(f'小节 {bar+1}')
            grid = [['---']*(project['meter']*4) for _ in track['tuning']]
            for n in track['notes']:
                if n.get('string') and int(n['beat']//project['meter']) == bar:
                    slot = int(round((n['beat']-bar*project['meter'])*4))
                    if slot < len(grid[0]): grid[n['string']-1][slot] = str(n['fret']).rjust(2, '-')+('?' if n.get('review') else '-')
            for pitch, row in zip(track['tuning'], grid):
                lines.append(f'{note_name(pitch):3}|'+''.join(row)+'|')
        unassigned = [n for n in track['notes'] if not n.get('string')]
        if unassigned:
            lines.append('未分配指法（音域/同时发声冲突）：')
            lines.extend(f"{n['start']:.3f}s {note_name(n['pitch'])}" for n in unassigned)
        lines.append('')
    return '\n'.join(lines).encode('utf8')
