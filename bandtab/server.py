"""Loopback-only server with bounded uploads, atomic storage and one inference worker."""
import concurrent.futures
import json
import mimetypes
import os
from pathlib import Path
import re
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from . import demo, export
from .pipeline import transcribe, capabilities, Cancelled
from .score import options, validate_project, prepare

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT/'data'
LOCK = threading.RLock()
JOBS = {}
POOL = concurrent.futures.ThreadPoolExecutor(max_workers=1)
MAX_UPLOAD = 200*1024*1024


def save(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding='utf8')
    tmp.replace(path)


def project_dir(pid):
    if not re.fullmatch('[0-9a-f]{32}', pid):
        raise ValueError('无效项目编号')
    return DATA/pid


def load(pid):
    return json.loads((project_dir(pid)/'project.json').read_text(encoding='utf8'))


def run_job(pid, source, config, title):
    def update(progress, message):
        with LOCK:
            JOBS[pid].update(progress=progress, message=message, status='running')
    def check():
        if JOBS[pid]['cancel'].is_set():
            raise Cancelled()
    try:
        check()
        p = transcribe(source, project_dir(pid), config, update, check)
        p['title'] = title
        with LOCK:
            save(project_dir(pid)/'project.json', p)
            JOBS[pid].update(status='done', progress=100, message='谱子已生成')
    except Cancelled:
        with LOCK: JOBS[pid].update(status='cancelled', message='任务已取消')
    except Exception as e:
        (project_dir(pid)/'error.log').write_text(traceback.format_exc(), encoding='utf8')
        with LOCK: JOBS[pid].update(status='error', message=str(e))


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass

    def send(self, status, payload, content_type='application/json; charset=utf-8', headers=None):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf8')
        if isinstance(payload, str): payload = payload.encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(payload))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        for key, value in (headers or {}).items(): self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def local_request(self):
        host = self.headers.get('Host', '')
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        if host not in allowed: raise ValueError('只允许本机访问')
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://{h}' for h in allowed}:
            raise ValueError('拒绝跨站请求')

    def body(self, limit=8*1024*1024):
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= limit: raise ValueError('请求为空或超过大小限制')
        content = self.rfile.read(length)
        if len(content) != length: raise ValueError('上传不完整')
        return content

    def do_GET(self):
        try:
            self.local_request()
            parsed = urlparse(self.path)
            path = parsed.path
            if path == '/api/health': return self.send(200, capabilities())
            if path == '/api/projects':
                projects = []
                with LOCK:
                    for f in sorted(DATA.glob('*/project.json'), key=lambda f: f.stat().st_mtime, reverse=True):
                        p = json.loads(f.read_text(encoding='utf8'))
                        projects.append({k: p[k] for k in ('id', 'title', 'duration', 'bpm', 'mode')})
                return self.send(200, projects)
            match = re.fullmatch('/api/jobs/([0-9a-f]{32})', path)
            if match:
                with LOCK:
                    job = JOBS.get(match[1])
                    if not job: return self.send(404, dict(error='任务不存在，服务可能已重启，请查看项目历史。'))
                    return self.send(200, {k: v for k, v in job.items() if k != 'cancel'})
            match = re.fullmatch('/api/projects/([0-9a-f]{32})(?:/(.*))?', path)
            if match:
                pid, action = match[1], match[2]
                with LOCK: p = load(pid)
                if not action: return self.send(200, p)
                if action == 'export':
                    fmt = parse_qs(parsed.query).get('format', ['json'])[0]
                    if fmt == 'json': payload, mime = json.dumps(p, ensure_ascii=False, indent=2).encode(), 'application/json'
                    elif fmt == 'midi': payload, mime = export.midi(p), 'audio/midi'
                    elif fmt == 'musicxml': payload, mime = export.musicxml(p), 'application/vnd.recordare.musicxml+xml'
                    elif fmt == 'txt': payload, mime = export.text_tab(p), 'text/plain; charset=utf-8'
                    else: raise ValueError('未知导出格式')
                    extension = 'mid' if fmt == 'midi' else fmt
                    return self.send(200, payload, mime, {'Content-Disposition': f'attachment; filename="bandtab.{extension}"'})
                if action == 'audio':
                    track = parse_qs(parsed.query).get('track', ['mix'])[0]
                    relative = p['audio'] if track == 'mix' else next(t['audio'] for t in p['tracks'] if t['id'] == track)
                    return self.file(project_dir(pid)/relative, ranged=True)
            static = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
            if path in static: return self.file(ROOT/'web'/static[path])
            self.send(404, dict(error='找不到内容'))
        except (FileNotFoundError, StopIteration): self.send(404, dict(error='项目或文件不存在'))
        except (ValueError, KeyError) as e: self.send(400, dict(error=str(e)))
        except (BrokenPipeError, ConnectionResetError): pass
        except Exception:
            traceback.print_exc(); self.send(500, dict(error='服务异常，请查看终端日志'))

    def file(self, path, ranged=False):
        total = path.stat().st_size
        start, end, status = 0, total-1, 200
        value = self.headers.get('Range') if ranged else None
        if value:
            m = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
            if not m or not any(m.groups()): return self.send(416, b'', headers={'Content-Range': f'bytes */{total}'})
            if m[1]: start, end = int(m[1]), min(int(m[2]) if m[2] else end, end)
            else: start = max(0, total-int(m[2]))
            if start > end or start >= total: return self.send(416, b'', headers={'Content-Range': f'bytes */{total}'})
            status = 206
        self.send_response(status)
        self.send_header('Content-Type', mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
        self.send_header('Content-Length', end-start+1)
        self.send_header('X-Content-Type-Options', 'nosniff')
        if ranged: self.send_header('Accept-Ranges', 'bytes')
        else: self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        if status == 206: self.send_header('Content-Range', f'bytes {start}-{end}/{total}')
        self.end_headers()
        with path.open('rb') as f:
            f.seek(start); remaining = end-start+1
            while remaining:
                chunk = f.read(min(65536, remaining))
                if not chunk: break
                self.wfile.write(chunk); remaining -= len(chunk)

    def do_POST(self):
        try:
            self.local_request()
            parsed = urlparse(self.path)
            if parsed.path == '/api/demo':
                pid = uuid.uuid4().hex
                folder = project_dir(pid); folder.mkdir(parents=True)
                p = demo.create(folder)
                with LOCK: save(folder/'project.json', p)
                return self.send(201, p)
            if parsed.path == '/api/transcribe':
                query = parse_qs(parsed.query)
                filename = Path(query.get('filename', ['audio.wav'])[0]).name
                suffix = Path(filename).suffix.lower()
                if suffix not in ('.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac', '.aiff', '.opus'):
                    raise ValueError('不支持此文件格式')
                config = options(json.loads(query.get('options', ['{}'])[0]))
                with LOCK:
                    if sum(j['status'] in ('queued', 'running') for j in JOBS.values()) >= 3:
                        self.close_connection = True
                        return self.send(429, dict(error='已有三个任务等待处理，请稍后再试。'))
                content = self.body(MAX_UPLOAD)
                pid = uuid.uuid4().hex
                folder = project_dir(pid); folder.mkdir(parents=True)
                source = folder/('source'+suffix); source.write_bytes(content)
                with LOCK: JOBS[pid] = dict(id=pid, status='queued', progress=0, message='等待处理', cancel=threading.Event())
                POOL.submit(run_job, pid, source, config, Path(filename).stem[:160])
                return self.send(202, dict(id=pid))
            match = re.fullmatch('/api/jobs/([0-9a-f]{32})/cancel', parsed.path)
            if match:
                with LOCK:
                    if match[1] not in JOBS: return self.send(404, dict(error='任务不存在'))
                    JOBS[match[1]]['cancel'].set()
                return self.send(200, dict(ok=True))
            match = re.fullmatch('/api/projects/([0-9a-f]{32})(/refinger)?', parsed.path)
            if match:
                raw = json.loads(self.body())
                with LOCK:
                    p = validate_project(raw, load(match[1]))
                    if match[2]: prepare(p)
                    save(project_dir(match[1])/'project.json', p)
                return self.send(200, p)
            self.send(404, dict(error='找不到操作'))
        except (ValueError, KeyError, TypeError) as e:
            self.close_connection = True
            self.send(400, dict(error=str(e)))
        except (BrokenPipeError, ConnectionResetError): pass
        except Exception:
            traceback.print_exc(); self.send(500, dict(error='服务异常，请查看终端日志'))


def serve(port=8765):
    DATA.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    print(f'BandTab Studio 已启动：http://127.0.0.1:{port}', flush=True)
    print('仅在本机处理音频。Ctrl+C 退出。', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        for j in JOBS.values(): j['cancel'].set()
        server.server_close(); POOL.shutdown(wait=False, cancel_futures=True)
