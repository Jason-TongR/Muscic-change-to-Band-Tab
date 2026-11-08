#!/usr/bin/env python3
"""Validate the actual Windows ZIP and installer, outside the build environment."""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.build_desktop import sha256

APP_ID='{C893045E-E753-491D-93B0-FD1EF9088E15}_is1'


def run_process(command,cwd,env,log,timeout=900):
    label=Path(log).stem
    print('Starting '+label,flush=True)
    with Path(log).open('w',encoding='utf8') as stream:
        process=subprocess.Popen([str(x) for x in command],cwd=cwd,env=env,
            stdout=stream,stderr=stream,creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+timeout
        try:
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise subprocess.TimeoutExpired(command,timeout)
                try:
                    code=process.wait(timeout=min(30,remaining));break
                except subprocess.TimeoutExpired:
                    print('Waiting for '+label,flush=True)
                    recent=Path(log).read_text(encoding='utf8',errors='replace').splitlines()
                    if recent:print(recent[-1][-800:],flush=True)
        except subprocess.TimeoutExpired:
            subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),
                '/PID',str(process.pid),'/T','/F'],capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW)
            process.wait(timeout=15)
            raise RuntimeError('Timed out: '+str(command[0]))
    if code:raise RuntimeError(f'{Path(command[0]).name} exited with {code}; see {log}')
    print('Finished '+label,flush=True)


def registry_value(key,name=''):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as handle:
            return winreg.QueryValueEx(handle,name)[0]
    except FileNotFoundError:return None


def assert_x64_executable(path):
    with Path(path).open('rb') as stream:
        if stream.read(2)!=b'MZ':raise ValueError('Not a Windows executable')
        stream.seek(0x3c);offset=struct.unpack('<I',stream.read(4))[0]
        stream.seek(offset)
        if stream.read(4)!=b'PE\0\0' or struct.unpack('<H',stream.read(2))[0]!=0x8664:
            raise ValueError('The portable application must be a native x64 PE executable')


def isolated_environment(home):
    env=os.environ.copy()
    for key in ('PYTHONHOME','PYTHONPATH','VIRTUAL_ENV','BANDTAB_MODEL_HOME','NUMBA_CACHE_DIR','MPLCONFIGDIR'):
        env.pop(key,None)
    # os.environ is case-insensitive on Windows; its plain dict copy is not.
    system=Path(next(value for key,value in env.items() if key.upper()=='SYSTEMROOT'))
    env.update(PATH=os.pathsep.join(str(p) for p in (system/'System32',system)),
        BANDTAB_HOME=str(home),BANDTAB_OFFLINE='1',PYTHONNOUSERSITE='1',
        QT_QPA_PLATFORM='windows',PYTHONUTF8='1',OMP_NUM_THREADS='2',
        OPENBLAS_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
    return env


def check_app(executable,home,cwd,output,name,ai=False):
    home.mkdir(parents=True,exist_ok=True)
    command=[executable,'--self-test']+(['--ai'] if ai else [])
    try:
        run_process(command,cwd,isolated_environment(home),output/(name+'-process.log'),timeout=780 if ai else 180)
    finally:
        for file in home.glob('*'):
            if file.suffix in ('.log','.json','.png') and file.is_file():
                shutil.copy2(file,output/(name+'-'+file.name))
    report=json.loads((home/'self-test-report.json').read_text(encoding='utf8'))
    expected=['native_window','project_roundtrip','unicode_paths','temporary_files_released',
        'frozen_worker_band' if ai else 'worker_transcription']
    if any(report.get(key)!='pass' for key in expected):raise RuntimeError(f'{name} failed: {report}')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--release',type=Path,default=ROOT/'release')
    parser.add_argument('--output',type=Path,default=ROOT/'data/windows-validation')
    args=parser.parse_args()
    if sys.platform!='win32':parser.error('Run this verification on Windows x64.')
    if registry_value('Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\'+APP_ID,'UninstallString'):
        parser.error('An existing BandTab installation was found. Run installer tests on a clean Windows machine.')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    result={'status':'running','platform':sys.platform,'checks':{}}
    work=Path(tempfile.mkdtemp(prefix='BandTab Windows 中文 ',dir=output))
    installed=work/'安装 程序';uninstaller=installed/'unins000.exe'
    cwd=work/'空白 工作目录';cwd.mkdir()
    home=work/'用户 数据';home.mkdir()
    sentinel=home/'keep-user-project.txt';sentinel.write_text('retain this user project',encoding='utf8')
    installer_started=False
    try:
        release=args.release.resolve()
        names=['BandTabStudio-Windows-x64-Portable.zip','BandTabStudio-Windows-x64-Setup.exe','原创练习曲.bandtab']
        hashes=json.loads((release/'SHA256SUMS.json').read_text(encoding='utf8'))
        for name in names:
            if sha256(release/name)!=hashes.get(name):raise ValueError('Checksum mismatch: '+name)
        result['checks']['release_checksums']='pass'
        portable=work/'便携 程序';portable.mkdir()
        with zipfile.ZipFile(release/names[0]) as archive:archive.extractall(portable)
        executable=portable/'BandTabStudio/BandTabStudio.exe'
        assert_x64_executable(executable)
        internal=executable.parent/'_internal'
        assert list((internal/'PySide6').rglob('qwindows.dll')), 'Windows Qt platform plugin is missing'
        assert (internal/'bundled_models/5c90dfd2-34c22ccb.th').is_file()
        result['checks']['portable']=check_app(executable,work/'便携 用户',cwd,output,'portable')
        installer=release/names[1]
        group='BandTab Studio Check '+work.name.rsplit(' ',1)[-1]
        install_command=[installer,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',
            '/LANG=chinesesimplified','/DIR='+str(installed),'/GROUP='+group,'/TASKS=associate',
            '/LOG='+str(output/'installer.log')]
        installer_started=True
        run_process(install_command,cwd,os.environ.copy(),output/'installer-process.log',600)
        assert (installed/'BandTabStudio.exe').is_file()
        command=registry_value('Software\\Classes\\BandTabStudio.Project\\shell\\open\\command')
        assert command==f'"{installed / "BandTabStudio.exe"}" --open "%1"', command
        shortcut=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs'/group/'BandTab Studio.lnk'
        assert shortcut.is_file(), 'Start menu shortcut is missing'
        result['checks']['per_user_install_and_file_open_command']='pass'
        result['checks']['installed']=check_app(installed/'BandTabStudio.exe',home,cwd,output,'installed',ai=True)
        run_process(install_command,cwd,os.environ.copy(),output/'upgrade-process.log',600)
        assert sentinel.read_text(encoding='utf8')=='retain this user project'
        result['checks']['upgrade_preserves_library']='pass'
        run_process([uninstaller,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',
            '/LOG='+str(output/'uninstaller.log')],cwd,os.environ.copy(),output/'uninstaller-process.log',300)
        deadline=time.monotonic()+20
        # Inno's launcher can return while its helper finishes deleting itself.
        while ((installed/'BandTabStudio.exe').exists() or uninstaller.exists()) and time.monotonic()<deadline:
            time.sleep(.2)
        assert not (installed/'BandTabStudio.exe').exists()
        assert not uninstaller.exists(), 'Uninstaller self-cleanup did not finish'
        assert registry_value('Software\\Classes\\BandTabStudio.Project\\shell\\open\\command') is None
        assert not shortcut.exists()
        assert sentinel.read_text(encoding='utf8')=='retain this user project'
        result['checks']['uninstall_preserves_library']='pass'
        installer_started=False
        result['status']='pass'
    except Exception:
        result['status']='fail';result['error']=traceback.format_exc()
    finally:
        # Only uninstall the temporary installation created by this test.
        if installer_started and uninstaller.is_file():
            try:run_process([uninstaller,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],
                cwd,os.environ.copy(),output/'cleanup-process.log',300)
            except Exception:
                result['cleanup_error']=traceback.format_exc()
                result['status']='fail'
        (output/'windows-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        if result['status']=='pass':shutil.rmtree(work)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='pass' else 1


if __name__=='__main__':raise SystemExit(main())
