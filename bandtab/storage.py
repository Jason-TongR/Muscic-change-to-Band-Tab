"""Desktop storage and self-contained project exchange; no HTTP dependency."""
import copy
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
import uuid
import zipfile
from .score import validate_project, finite


def user_data_dir():
    if os.environ.get('BANDTAB_HOME'):
        return Path(os.environ['BANDTAB_HOME']).expanduser().resolve()
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData'/'Local'))/'BandTab Studio'
    if sys.platform == 'darwin':
        return Path.home()/'Library'/'Application Support'/'BandTab Studio'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local'/'share'))/'bandtab-studio'


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique temporary file so background jobs and the UI never share a temp name.
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf8') as f:
            json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def safe_asset(folder, name):
    pure = PurePosixPath(str(name).replace('\\', '/'))
    if pure.is_absolute() or '..' in pure.parts or not pure.parts or ':' in str(pure):
        raise ValueError('项目包含不安全的文件路径')
    path = (Path(folder)/str(pure)).resolve()
    if not path.is_relative_to(Path(folder).resolve()):
        raise ValueError('项目文件超出了项目目录')
    return path


def validate_document(raw):
    """Validate imported metadata before drawing or opening referenced files."""
    p = copy.deepcopy(raw)
    if p.get('version') != 1: raise ValueError('不支持的项目版本')
    p['duration'] = finite(p['duration'], .1, 901, '音频长度')
    p['bpm'] = finite(p['bpm'], 30, 300, 'BPM')
    if not isinstance(p['beats'], list) or not 2 <= len(p['beats']) <= 10000:
        raise ValueError('无效节拍数据')
    p['beats'] = [finite(t, 0, 1000, '拍点') for t in p['beats']]
    if any(a >= b for a, b in zip(p['beats'], p['beats'][1:])): raise ValueError('拍点必须递增')
    if not 1 <= len(p['tracks']) <= 16: raise ValueError('声部数量不合理')
    ids = set()
    for t in p['tracks']:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', t['id']) or t['id'] in ids:
            raise ValueError('无效或重复声部编号')
        ids.add(t['id'])
        if t['instrument'] not in ('guitar','bass','piano','vocals','drums','other'):
            raise ValueError('无效乐器')
        t['name'] = str(t['name'])[:80]
        if t.get('tuning'):
            if not 1 <= len(t['tuning']) <= 8: raise ValueError('无效调弦')
            t['tuning'] = [int(finite(v, 0, 127, '调弦')) for v in t['tuning']]
        t['capo'] = int(finite(t.get('capo', 0), 0, 12, '变调夹'))
    p['waveform'] = [finite(v, 0, 2, '波形') for v in p.get('waveform', [])[:4000]]
    p['warnings'] = [str(v)[:1000] for v in p.get('warnings', [])[:30]]
    p['chords'] = [dict(start=finite(c['start'],0,1000,'和弦时间'),
                        end=finite(c['end'],0,1000,'和弦时间'), label=str(c['label'])[:20])
                   for c in p.get('chords', [])[:10000]]
    return validate_project(p, p)


class Library:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else user_data_dir()
        self.projects = self.root/'projects'
        self.projects.mkdir(parents=True, exist_ok=True)

    def folder(self, pid):
        if not re.fullmatch('[a-f0-9]{32}', pid): raise ValueError('无效项目编号')
        return self.projects/pid

    def create_folder(self):
        folder = self.folder(uuid.uuid4().hex); folder.mkdir()
        return folder

    def save(self, project):
        atomic_json(self.folder(project['id'])/'project.json', project)

    def load(self, pid):
        p = validate_document(json.loads((self.folder(pid)/'project.json').read_text(encoding='utf8')))
        p['id'] = pid
        for name in [p['audio']] + [t['audio'] for t in p['tracks']]:
            if not safe_asset(self.folder(pid), name).is_file(): raise ValueError('项目音频缺失，请重新导入完整项目包')
        return p

    def entries(self):
        entries = []
        for f in sorted(self.projects.glob('*/project.json'), key=lambda p:p.stat().st_mtime, reverse=True):
            try:
                p = json.loads(f.read_text(encoding='utf8'))
                entries.append(dict(id=f.parent.name, title=str(p['title']), bpm=p['bpm'], duration=p['duration']))
            except (ValueError, KeyError, OSError): continue
        return entries

    def asset(self, p, track=None):
        return safe_asset(self.folder(p['id']), p['audio'] if track is None else track['audio'])

    def export_package(self, project, target, check=lambda:None):
        p = copy.deepcopy(project)
        paths = {'mix': self.asset(p)}
        paths.update({t['id']: self.asset(p, t) for t in p['tracks']})
        target = Path(target)
        tmp = target.with_name(target.name+'.partial')
        try:
            with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
                mapped = {}
                for key, file in paths.items():
                    check()
                    if file not in mapped:
                        mapped[file] = f'audio/{len(mapped)}{file.suffix.lower()}'
                        z.write(file, mapped[file])
                    if key == 'mix': p['audio'] = mapped[file]
                    else: next(t for t in p['tracks'] if t['id'] == key)['audio'] = mapped[file]
                z.writestr('project.json', json.dumps(p, ensure_ascii=False, allow_nan=False))
            os.replace(tmp, target)
        finally:
            if tmp.exists(): tmp.unlink()

    def import_package(self, source, check=lambda:None):
        folder = self.create_folder()
        try:
            with zipfile.ZipFile(source) as z:
                infos = z.infolist()
                if len(infos)>100 or sum(i.file_size for i in infos)>2*1024**3:
                    raise ValueError('项目包过大')
                names = [i.filename for i in infos]
                if len(names) != len(set(names)): raise ValueError('项目包包含重复文件')
                for info in infos:
                    safe_asset(folder, info.filename)
                    if (info.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError('项目包不允许符号链接')
                if z.getinfo('project.json').file_size > 16*1024**2: raise ValueError('谱面数据过大')
                p = validate_document(json.loads(z.read('project.json')))
                assets = set([p['audio']]+[t['audio'] for t in p['tracks']])
                for name in assets:
                    check()
                    dest = safe_asset(folder, name)
                    if dest.suffix.lower() != '.wav': raise ValueError('项目音轨应为 WAV 文件')
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(name) as src, dest.open('wb') as out: shutil.copyfileobj(src, out, 1024*1024)
            p['id'] = folder.name
            self.save(p)
            return p
        except BaseException:
            shutil.rmtree(folder)
            raise

    def import_legacy(self, file):
        source = Path(file)
        p = validate_document(json.loads(source.read_text(encoding='utf8')))
        folder = self.create_folder()
        try:
            mapping = {}
            for name in set([p['audio']]+[t['audio'] for t in p['tracks']]):
                file = safe_asset(source.parent, name)
                if not file.is_file(): raise ValueError('原项目的音频文件缺失')
                relative = f'audio/{len(mapping)}.wav'
                dest = folder/relative;dest.parent.mkdir(exist_ok=True)
                shutil.copy2(file, dest);mapping[name] = relative
            p['audio'] = mapping[p['audio']]
            for t in p['tracks']:t['audio'] = mapping[t['audio']]
            p['id'] = folder.name;self.save(p);return p
        except BaseException:
            shutil.rmtree(folder);raise
