#!/usr/bin/env python3
"""Run the local rehearsal app, or transcribe audio from the command line."""
from pathlib import Path
import os
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'.vendor'))
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMBA_NUM_THREADS'):
    os.environ.setdefault(variable, str(min(4, os.cpu_count() or 1)))
os.environ.setdefault('NUMBA_CACHE_DIR', str(ROOT/'data'/'cache'))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'data'/'cache'/'matplotlib'))


def main():
    import argparse
    p = argparse.ArgumentParser(description='BandTab Studio · 音乐转动态乐队谱')
    p.add_argument('audio', nargs='?', help='音频路径；留空打开本地服务')
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--mode', choices=['preview', 'instrument', 'band'], default='preview')
    p.add_argument('--instrument', choices=['guitar', 'bass', 'piano', 'vocals'], default='guitar')
    p.add_argument('--bpm', type=float, default=0)
    p.add_argument('--tuning', choices=['standard', 'drop_d', 'half_down'], default='standard')
    p.add_argument('--capo', type=int, default=0)
    p.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    args = p.parse_args()
    try:
        if args.audio:
            import uuid
            from bandtab.pipeline import transcribe
            from bandtab.server import DATA, save
            from bandtab.export import midi, musicxml, text_tab
            directory = DATA/uuid.uuid4().hex; directory.mkdir(parents=True)
            result = transcribe(Path(args.audio).resolve(), directory, vars(args), lambda n, s: print(f'{n:3}% {s}', flush=True))
            save(directory/'project.json', result)
            (directory/'score.mid').write_bytes(midi(result))
            (directory/'score.musicxml').write_bytes(musicxml(result))
            (directory/'score.txt').write_bytes(text_tab(result))
            print(f'完成：{directory}\n启动 python app.py 后也可在项目历史中打开。')
        else:
            from bandtab.server import serve
            serve(args.port)
    except ImportError as e:
        print(f'缺少依赖：{e}。请先运行 bash scripts/install.sh', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'无法完成：{e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
