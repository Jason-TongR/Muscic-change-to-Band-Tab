# Build on each target OS. The application includes AI runtimes and local models.
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata, get_package_paths
ROOT=Path(SPECPATH).parent
hidden=['demucs.separate','demucs.htdemucs','basic_pitch.inference','onnxruntime','soundfile',
        'scipy.special._ufuncs','PySide6.QtMultimedia','bandtab.desktop.smoke']
datas=[(str(ROOT/'assets'/'icon.png'),'assets'),(str(ROOT/'docs'/'DESKTOP.md'),'docs'),(str(ROOT/'packaging'/'THIRD_PARTY.md'),'licenses')]
for package in ['librosa','resampy','demucs','basic_pitch','onnxruntime','imageio_ffmpeg','lazy_loader']:
    datas+=collect_data_files(package)
# librosa uses lazy_loader.attach_stub: stubs and all dynamically imported modules are needed.
hidden+=collect_submodules('librosa',filter=lambda x:'.tests' not in x)
hidden+=collect_submodules('demucs',filter=lambda x:not any(y in x for y in ('.train','.test','.evaluate','.distrib')))
for package in ['basic-pitch','demucs','librosa','resampy','onnxruntime','einops','soundfile','imageio-ffmpeg','scikit-learn']:
    datas+=copy_metadata(package)
# Include licenses for bundled dependencies. Dynamic libraries remain replaceable (onedir).
import importlib.metadata
for dist in importlib.metadata.distributions():
    for file in dist.files or []:
        if any(word in str(file).lower() for word in ('license','copying','notice')) and '.dist-info/' in str(file):
            path=dist.locate_file(file)
            if path.is_file():datas.append((str(path),'licenses/'+dist.metadata['Name']))
model=ROOT/'data'/'models'/'hub'/'checkpoints'/'5c90dfd2-34c22ccb.th'
if model.exists():datas.append((str(model),'bundled_models'))
a=Analysis([str(ROOT/'desktop.py')],pathex=[str(ROOT)],binaries=[],datas=datas,hiddenimports=hidden,
    hookspath=[str(ROOT/'packaging'/'hooks')],runtime_hooks=[],
    excludes=['tensorflow','keras','coremltools','tflite_runtime','matplotlib','IPython','pytest','tkinter','torchvision','torchaudio.prototype'],
    module_collection_mode={'librosa':'pyz+py','resampy':'pyz+py','numba':'pyz+py','demucs':'pyz+py','torch':'pyz+py'},
    noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='BandTabStudio',debug=False,bootloader_ignore_signals=False,
    strip=False,upx=False,icon=str(ROOT/'assets'/'icon.ico') if sys.platform=='win32' else None,console=False,disable_windowed_traceback=False,argv_emulation=False,
    target_arch=None,codesign_identity=os.environ.get('BANDTAB_SIGN_IDENTITY'),entitlements_file=None)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='BandTabStudio')
if sys.platform=='darwin':
    app=BUNDLE(coll,name='BandTabStudio.app',icon=str(ROOT/'assets'/'icon.icns'),bundle_identifier='studio.bandtab.desktop',
        info_plist={'CFBundleShortVersionString':'0.2.0','NSHighResolutionCapable':True,
                    'NSHumanReadableCopyright':'BandTab Studio; see bundled third-party license notices.'})
