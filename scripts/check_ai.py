"""Optional integration check: real models on a short synthetic fixture.

Run after installing AI dependencies: .venv-ai/bin/python scripts/check_ai.py
This verifies engine execution, not transcription quality on real music.
"""
from pathlib import Path
import os
import sys
import uuid
import json
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import app
from bandtab import demo, audio
from bandtab.pipeline import transcribe
from bandtab.server import save

def main():
    folder=ROOT/'data'/'ai-check-fixture';folder.mkdir(parents=True,exist_ok=True)
    demo.create(folder)
    y,sr=audio.read_wav(folder/'audio.wav')
    audio.write_wav(folder/'short.wav',y[:4*sr],sr)
    target=ROOT/'data'/uuid.uuid4().hex;target.mkdir()
    p=transcribe(folder/'short.wav',target,{'mode':'band','bpm':108},lambda v,s:print(f'{v}% {s}',flush=True))
    assert len(p['tracks'])==6
    assert all((target/t['audio']).is_file() for t in p['tracks'])
    assert any(t['notes'] for t in p['tracks'] if t['instrument'] not in ('drums','other'))
    p['title']='AI 流程自检 · 4 秒合成音频'
    p['warnings'].insert(0,'此项目由真实模型转写合成混音，只验证引擎流程，不代表真实歌曲准确率。')
    save(target/'project.json',p)
    report={t['id']:len(t['notes']) for t in p['tracks']}
    print(json.dumps({'project':str(target),'notes':report},ensure_ascii=False),flush=True)
    (ROOT/'data'/'ai-check-report.json').write_text(json.dumps(report,indent=2),encoding='utf8')

if __name__=='__main__':main()
