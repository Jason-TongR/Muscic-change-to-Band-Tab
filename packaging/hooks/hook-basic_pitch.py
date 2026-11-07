# The shipped inference adapter explicitly selects ONNX. Exclude training backends.
from PyInstaller.utils.hooks import collect_data_files
hiddenimports=['basic_pitch.inference','basic_pitch.note_creation','basic_pitch.constants']
datas=collect_data_files('basic_pitch',includes=['saved_models/icassp_2022/nmp.onnx'])
excludedimports=['tensorflow','coremltools','tflite_runtime','basic_pitch.train','basic_pitch.models','basic_pitch.data']
