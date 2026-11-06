import copy
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import numpy as np
import app  # enables project-local optional decoder
from bandtab import audio, demo, export
from bandtab.pipeline import transcribe
from bandtab.score import assign_fingering, TUNINGS, validate_project, seconds_to_beats, beat_to_seconds


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()

    def test_transcribe_known_guitar_notes(self):
        sr=22050
        pitches=[40, 45, 50, 55, 59, 64, 69, 76]
        segments=[]
        for pitch in pitches:
            t=np.arange(int(sr*.4))/sr
            f=440*2**((pitch-69)/12)
            segments += [.35*(np.sin(2*np.pi*f*t)+.2*np.sin(4*np.pi*f*t))*np.minimum(1,t*100), np.zeros(int(sr*.12))]
        path=self.root/'known.wav'; audio.write_wav(path,np.concatenate(segments))
        out=self.root/'result'; out.mkdir()
        p=transcribe(path,out,{'bpm':115.38})
        actual=[n['pitch'] for n in p['tracks'][0]['notes']]
        self.assertEqual(actual,pitches)
        self.assertTrue(all(n['review'] for n in p['tracks'][0]['notes']))
        self.assertEqual(len(p['tracks']),1)  # no invented band stems
        self.assertLess(abs(p['tracks'][0]['notes'][0]['start']),.08)

    def test_silence_does_not_create_notes(self):
        self.assertEqual(audio.melody(np.zeros(22050),22050),[])
        self.assertEqual(audio.drum_notes(np.zeros(22050),22050),[])

    def test_simultaneous_and_sustained_notes_use_unique_strings(self):
        notes=[dict(start=0,end=1,pitch=p) for p in [40,47,52,56,59,64]]
        notes += [dict(start=.5,end=1.1,pitch=67)]
        assign_fingering(notes,TUNINGS['standard'])
        first=[n for n in notes if n['start']==0]
        self.assertEqual(len({n['string'] for n in first}),6)
        self.assertIsNone(notes[-1]['string'])
        self.assertTrue(notes[-1]['review'])
        for n in first:self.assertEqual(TUNINGS['standard'][n['string']-1]+n['fret'],n['pitch'])

    def test_capo_and_out_of_range(self):
        notes=[dict(start=i,end=i+.2,pitch=p) for i,p in enumerate([30,42,66])]
        assign_fingering(notes,TUNINGS['standard'],capo=2)
        self.assertIsNone(notes[0]['string'])
        for n in notes[1:]:self.assertEqual(TUNINGS['standard'][n['string']-1]+2+n['fret'],n['pitch'])

    def test_variable_beat_roundtrip(self):
        beats=[.2,.7,1.25,1.8,2.4]
        for t in [0,.2,.5,1,2,3]:
            self.assertAlmostEqual(beat_to_seconds(seconds_to_beats(t,beats,120),beats,120),t)

    def test_validation_rejects_bad_fields_and_keeps_audio_paths(self):
        p=demo.create(self.root)
        raw=copy.deepcopy(p);raw['audio']='../../secret';raw['tracks'][0]['audio']='../../secret'
        result=validate_project(raw,p)
        self.assertEqual(result['audio'],'audio.wav')
        self.assertEqual(result['tracks'][0]['audio'],'guitar.wav')
        for value in [float('nan'),float('inf'),-1]:
            raw=copy.deepcopy(p);raw['tracks'][0]['notes'][0]['start']=value
            with self.assertRaises(ValueError):validate_project(raw,p)
        raw=copy.deepcopy(p);raw['tracks'][0]['notes'][0]['fret']=24
        with self.assertRaises(ValueError):validate_project(raw,p)

    def test_midi_valid_chunks_and_timing(self):
        p=demo.create(self.root)
        data=export.midi(p)
        self.assertEqual(data[:4],b'MThd')
        _,fmt,count,ppq=struct.unpack('>IHHH',data[4:14]);self.assertEqual((fmt,count,ppq),(1,4,960))
        cursor=14
        for i in range(count):
            self.assertEqual(data[cursor:cursor+4],b'MTrk')
            length=struct.unpack('>I',data[cursor+4:cursor+8])[0]
            self.assertEqual(data[cursor+8+length-4:cursor+8+length],b'\x00\xff\x2f\x00')
            cursor+=8+length
        self.assertEqual(cursor,len(data))

    def test_musicxml_bar_balance_and_cross_bar_ties(self):
        p=demo.create(self.root)
        n=p['tracks'][0]['notes'][0];n['beat']=3.5;n['length']=2
        root=ET.fromstring(export.musicxml(p))
        self.assertEqual(len(root.findall('part')),3)
        self.assertTrue(root.findall('.//technical/string'))
        self.assertTrue(root.findall('.//tie[@type="start"]'))
        self.assertTrue(root.findall('.//tie[@type="stop"]'))
        for measure in root.findall('.//measure'):
            clock=0
            for child in measure:
                if child.tag=='note':clock+=int(child.findtext('duration'))
                elif child.tag=='backup':
                    self.assertEqual(clock,16);clock-=int(child.findtext('duration'))
            self.assertEqual(clock,16)

    def test_manual_review_clear_is_persisted(self):
        p=demo.create(self.root)
        p['tracks'][0]['notes'][0]['confidence']=.2
        p['tracks'][0]['notes'][0]['review']=True
        raw=copy.deepcopy(p);raw['tracks'][0]['notes'][0]['review']=False
        self.assertFalse(validate_project(raw,p)['tracks'][0]['notes'][0]['review'])

    def test_manual_tempo_changes_grid_not_note_times(self):
        p=demo.create(self.root);raw=copy.deepcopy(p);raw['bpm']=90;raw['offset']=.2
        result=validate_project(raw,p)
        self.assertEqual(result['beat_source'],'manual')
        self.assertEqual(result['tracks'][0]['notes'][0]['start'],p['tracks'][0]['notes'][0]['start'])
        self.assertAlmostEqual(result['beats'][1]-result['beats'][0],2/3,places=5)

if __name__=='__main__':unittest.main()
