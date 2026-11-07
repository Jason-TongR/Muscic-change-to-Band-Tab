#!/usr/bin/env python3
"""Build on the target OS; Windows full builds require an installer compiler."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from bandtab import __version__


def find_inno():
    configured=os.environ.get('ISCC')
    candidates=[configured] if configured else []
    candidates.append(shutil.which('ISCC'))
    for variable,default in [('ProgramFiles(x86)','C:/Program Files (x86)'),('ProgramFiles','C:/Program Files')]:
        candidates.append(str(Path(os.environ.get(variable,default))/'Inno Setup 6'/'ISCC.exe'))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():return Path(candidate)
    return None


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def checksums(release):
    hashes={file.name:sha256(file) for file in sorted(release.iterdir())
        if file.is_file() and file.suffix in ('.zip','.gz','.dmg','.exe','.bandtab')}
    (release/'SHA256SUMS.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return hashes


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--skip-model',action='store_true')
    parser.add_argument('--archive',action='store_true')
    parser.add_argument('--require-installer',action='store_true')
    args=parser.parse_args()
    system=platform.system()
    if args.require_installer and system!='Windows':parser.error('--require-installer needs Windows')
    compiler=find_inno() if system=='Windows' else None
    if args.require_installer and not compiler:
        raise SystemExit('Install Inno Setup 6.5+ from https://jrsoftware.org/isdl.php or set ISCC to ISCC.exe.')
    if compiler and not (compiler.parent/'Languages/ChineseSimplified.isl').is_file():
        raise SystemExit('The installer requires Inno Setup 6.5+ with Languages/ChineseSimplified.isl.')
    os.chdir(ROOT)
    os.environ['BANDTAB_MODEL_HOME']=str(ROOT/'data/models')
    if not args.skip_model:
        from bandtab.runtime import ensure_model
        ensure_model(lambda n,s:print(s,flush=True))
    env=os.environ.copy();env['PYINSTALLER_CONFIG_DIR']=str(ROOT/'.cache/pyinstaller')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','packaging/BandTabStudio.spec'],env=env,check=True)
    bundle=ROOT/'dist/BandTabStudio'
    shutil.copy2(ROOT/'docs/DESKTOP.md',bundle/'使用说明.md')
    shutil.copy2(ROOT/'packaging/THIRD_PARTY.md',bundle/'THIRD_PARTY.md')
    if system=='Windows':
        shutil.copy2(ROOT/'packaging/README-Windows.txt',bundle/'使用说明-Windows.txt')
    if system=='Linux':
        launcher=bundle/'启动BandTab.sh'
        launcher.write_text('#!/usr/bin/env bash\nset -e\ncd "$(dirname "$0")"\nexec ./BandTabStudio "$@"\n')
        launcher.chmod(0o755)
    release=ROOT/'release';release.mkdir(exist_ok=True)
    name=f'BandTabStudio-{system}-{platform.machine()}'
    if system=='Windows':name='BandTabStudio-Windows-x64-Portable'
    if system=='Linux':name+='-glibc'+platform.libc_ver()[1]
    if args.archive:
        if system=='Darwin':
            subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(ROOT/'dist/BandTabStudio.app'),str(release/(name+'.zip'))],check=True)
            subprocess.run(['hdiutil','create','-volname','BandTab Studio','-srcfolder',str(ROOT/'dist/BandTabStudio.app'),'-ov','-format','UDZO',str(release/(name+'.dmg'))],check=True)
        else:
            shutil.make_archive(str(release/name),'zip' if system=='Windows' else 'gztar',ROOT/'dist','BandTabStudio')
    if compiler:
        subprocess.run([str(compiler),'/DMyAppVersion='+__version__,str(ROOT/'packaging/windows.iss')],check=True)
    elif system=='Windows':
        print('Portable build only: Inno Setup is missing. Use --require-installer for a complete Windows release.')
    # The example is generated from our own synthetic riff, never from a user's audio.
    from bandtab import demo
    from bandtab.storage import Library
    with tempfile.TemporaryDirectory(prefix='bandtab-release-demo-') as temporary:
        library=Library(Path(temporary));project=demo.create(library.create_folder());library.save(project)
        library.export_package(project,release/'原创练习曲.bandtab')
    hashes=checksums(release)
    revision=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True).stdout.strip() if shutil.which('git') else ''
    report=dict(version=__version__,system=system,architecture=platform.machine(),
        python=platform.python_version(),source_revision=revision or None,
        packages={name:importlib.metadata.version(name) for name in ('PySide6','torch','onnxruntime','demucs','basic-pitch','pyinstaller')},
        sha256=hashes)
    (release/f'build-info-{system}-{platform.machine()}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Build complete:',release,flush=True)


if __name__=='__main__':main()
