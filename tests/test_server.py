import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.parse import urlencode
import app
from bandtab import demo, server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.old=server.DATA;server.DATA=Path(cls.tmp.name)
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.port=cls.http.server_port
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join();server.DATA=cls.old;cls.tmp.cleanup()
    def request(self,method,path,body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=20)
        if isinstance(body,dict):body=json.dumps(body).encode()
        conn.request(method,path,body,headers or {})
        r=conn.getresponse(); result=(r.status,dict(r.getheaders()),r.read());conn.close();return result
    def test_demo_save_range_exports(self):
        status,_,data=self.request('POST','/api/demo');self.assertEqual(status,201)
        p=json.loads(data);pid=p['id']
        status,headers,data=self.request('GET',f'/api/projects/{pid}/audio',headers={'Range':'bytes=0-43'})
        self.assertEqual(status,206);self.assertEqual(len(data),44);self.assertEqual(data[:4],b'RIFF')
        status,_,_=self.request('GET',f'/api/projects/{pid}/audio',headers={'Range':'bytes=99999999-'})
        self.assertEqual(status,416)
        p['title']='测试 <曲名>';p['tracks'][0]['notes'][0]['review']=True
        self.assertEqual(self.request('POST',f'/api/projects/{pid}',p)[0],200)
        for fmt,prefix in [('midi',b'MThd'),('musicxml',b'<?xml'),('json',b'{')]:
            status,_,data=self.request('GET',f'/api/projects/{pid}/export?format={fmt}')
            self.assertEqual(status,200);self.assertTrue(data.startswith(prefix))
        self.assertEqual(json.loads(self.request('GET',f'/api/projects/{pid}')[2])['title'],'测试 <曲名>')
    def test_origin_and_host_are_restricted(self):
        self.assertEqual(self.request('POST','/api/demo',headers={'Origin':'https://evil.example'})[0],400)
        self.assertEqual(self.request('GET','/api/health',headers={'Host':'evil.example'})[0],400)
        self.assertEqual(self.request('GET','/../../etc/passwd')[0],404)
    def test_actual_upload_to_transcription(self):
        folder=server.DATA/'fixture';folder.mkdir();demo.create(folder)
        content=(folder/'guitar.wav').read_bytes()
        query=urlencode({'filename':'我的吉他.wav','options':json.dumps({'mode':'preview','bpm':108})})
        status,_,data=self.request('POST','/api/transcribe?'+query,content)
        self.assertEqual(status,202);pid=json.loads(data)['id']
        for _ in range(100):
            job=json.loads(self.request('GET',f'/api/jobs/{pid}')[2])
            if job['status'] in ('done','error'):break
            time.sleep(.1)
        self.assertEqual(job['status'],'done',job)
        p=json.loads(self.request('GET',f'/api/projects/{pid}')[2])
        self.assertEqual(p['title'],'我的吉他')
        self.assertGreater(len(p['tracks'][0]['notes']),20)

if __name__=='__main__':unittest.main()
