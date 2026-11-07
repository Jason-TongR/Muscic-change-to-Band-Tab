# Third-party software

BandTab Studio includes separately licensed components. Their copyright and license files are collected under `licenses/` in each build. These components are not represented as original BandTab work.

- Qt / PySide6 / Shiboken: Qt LGPL v3 (or applicable component licenses). This application uses dynamically linked Qt libraries in a replaceable directory layout. Source, license information and rebuild instructions: https://www.qt.io/qt-for-python and https://code.qt.io/cgit/pyside/pyside-setup.git/ . Qt sources: https://code.qt.io/cgit/qt/ . Package version is pinned in requirements-desktop.txt. Replacing compatible Qt libraries or rebuilding is permitted under their license terms.
- PyTorch / torchaudio: BSD-style licenses. https://github.com/pytorch/pytorch and https://github.com/pytorch/audio
- Demucs model and implementation: upstream license and notices. https://github.com/facebookresearch/demucs
- Spotify Basic Pitch: Apache 2.0. https://github.com/spotify/basic-pitch
- ONNX Runtime: MIT. https://github.com/microsoft/onnxruntime
- NumPy / SciPy / librosa / resampy and dependencies: see their included license files.
- FFmpeg supplied by imageio-ffmpeg and Qt Multimedia: respective bundled binary licenses apply. https://ffmpeg.org/legal.html and https://github.com/imageio/imageio-ffmpeg

The package format deliberately retains separate dynamic libraries. Do not remove notices when redistributing. Before a public commercial release, review exact binary component licenses and distribution obligations; this development build is unsigned and has no claim of store certification.
