#!/usr/bin/env python3
"""Build a standalone, offline-capable application on the current target OS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser();p.add_argument('--skip-model',action='store_true');p.add_argument('--archive',action='store_true');args=p.parse_args()
    os.chdir(ROOT)
    os.environ['BANDTAB_MODEL_HOME']=str(ROOT/'data'/'models')
    if not args.skip_model:
        from bandtab.runtime import ensure_model
        ensure_model(lambda n,s:print(s,flush=True))
    env=os.environ.copy();env['PYINSTALLER_CONFIG_DIR']=str(ROOT/'.cache'/'pyinstaller')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','packaging/BandTabStudio.spec'],env=env,check=True)
    bundle=ROOT/'dist'/'BandTabStudio'
    shutil.copy2(ROOT/'docs'/'DESKTOP.md',bundle/'使用说明.md')
    shutil.copy2(ROOT/'packaging'/'THIRD_PARTY.md',bundle/'THIRD_PARTY.md')
    if sys.platform.startswith('linux'):
        launcher=bundle/'启动BandTab.sh'
        launcher.write_text('#!/usr/bin/env bash\nset -e\ncd "$(dirname "$0")"\nexec ./BandTabStudio "$@"\n')
        launcher.chmod(0o755)
    release=ROOT/'release';release.mkdir(exist_ok=True)
    system=platform.system();arch=platform.machine();name=f'BandTabStudio-{system}-{arch}'
    if system=='Linux':name+='-glibc'+platform.libc_ver()[1]
    if args.archive:
        if system=='Darwin':
            subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(ROOT/'dist'/'BandTabStudio.app'),str(release/(name+'.zip'))],check=True)
            subprocess.run(['hdiutil','create','-volname','BandTab Studio','-srcfolder',str(ROOT/'dist'/'BandTabStudio.app'),'-ov','-format','UDZO',str(release/(name+'.dmg'))],check=True)
        else:
            shutil.make_archive(str(release/name),'zip' if system=='Windows' else 'gztar',ROOT/'dist','BandTabStudio')
    if system=='Windows':
        compiler=shutil.which('ISCC') or str(Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Inno Setup 6'/'ISCC.exe')
        if Path(compiler).is_file():subprocess.run([compiler,str(ROOT/'packaging'/'windows.iss')],check=True)
        else:print('Inno Setup not installed; portable folder/zip built. Installer recipe: packaging/windows.iss')
    hashes={}
    for file in release.iterdir():
        if file.suffix in ('.zip','.gz','.dmg','.exe'):
            h=hashlib.sha256()
            with file.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            hashes[file.name]=h.hexdigest()
    (release/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2))
    print('Build complete:',ROOT/'dist',flush=True)

if __name__=='__main__':main()
