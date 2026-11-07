import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from bandtab import demo
from bandtab.storage import Library,safe_asset,user_data_dir,validate_document
from bandtab.runtime import worker_command,process_options


class DesktopStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.library=Library(self.root/'library')
        self.folder=self.library.create_folder();self.p=demo.create(self.folder);self.library.save(self.p)
    def tearDown(self):self.tmp.cleanup()
    def test_project_package_is_self_contained_and_portable(self):
        package=self.root/'song.bandtab';self.library.export_package(self.p,package)
        second=Library(self.root/'another-computer');p=second.import_package(package)
        self.assertNotEqual(p['id'],self.p['id'])
        self.assertEqual(p['tracks'][0]['notes'],self.p['tracks'][0]['notes'])
        for t in p['tracks']:
            self.assertEqual(second.asset(p,t).read_bytes(),self.library.asset(self.p,next(x for x in self.p['tracks'] if x['id']==t['id'])).read_bytes())
        self.assertEqual(second.load(p['id'])['title'],self.p['title'])
    def test_legacy_import_copies_audio_without_modifying_original(self):
        original=(self.folder/'project.json').read_bytes();p=self.library.import_legacy(self.folder/'project.json')
        self.assertNotEqual(p['id'],self.p['id']);self.assertEqual((self.folder/'project.json').read_bytes(),original)
        self.assertEqual(self.library.asset(p).read_bytes(),self.library.asset(self.p).read_bytes())
    def test_path_escape_is_rejected(self):
        for path in ['../outside.wav','/tmp/outside.wav','C:/outside.wav','audio/../../x','..\\outside.wav']:
            with self.assertRaises(ValueError):safe_asset(self.root,path)
    def test_zip_traversal_is_rejected_and_partial_folder_removed(self):
        count=len(list(self.library.projects.iterdir()));archive=self.root/'bad.bandtab'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape.wav','bad');z.writestr('project.json',json.dumps(self.p))
        with self.assertRaises(ValueError):self.library.import_package(archive)
        self.assertFalse((self.library.projects/'escape.wav').exists());self.assertEqual(len(list(self.library.projects.iterdir())),count)
    def test_duplicate_or_nonmonotonic_data_rejected(self):
        p=copy.deepcopy(self.p);p['beats']=[0,.5,.4]
        with self.assertRaises(ValueError):validate_document(p)
        p=copy.deepcopy(self.p);p['tracks'][1]['id']=p['tracks'][0]['id']
        with self.assertRaises(ValueError):validate_document(p)
    def test_missing_asset_is_rejected(self):
        (self.folder/'guitar.wav').unlink()
        with self.assertRaises(ValueError):self.library.load(self.p['id'])
    def test_data_override_and_source_worker(self):
        with patch.dict(os.environ,{'BANDTAB_HOME':str(self.root)}):self.assertEqual(user_data_dir(),self.root)
        command=worker_command('--worker','request.json');self.assertTrue(command[1].endswith('desktop.py'));self.assertEqual(command[-2:],['--worker','request.json'])
    def test_cancelled_worker_does_not_publish_project(self):
        import desktop
        folder=self.library.create_folder()
        (folder/'request.json').write_text(json.dumps(dict(source='missing.wav',title='cancel test',options={})))
        (folder/'cancel').touch()
        self.assertEqual(desktop.worker(folder/'request.json'),2)
        self.assertEqual(json.loads((folder/'status.json').read_text())['status'],'cancelled')
        self.assertFalse((folder/'project.json').exists())

    def test_frozen_worker_does_not_call_python_module_mode(self):
        with patch('sys.frozen',True,create=True),patch('sys.executable','/test/BandTabStudio'):
            self.assertEqual(worker_command('--demucs-worker','-n','htdemucs_6s'),['/test/BandTabStudio','--demucs-worker','-n','htdemucs_6s'])

if __name__=='__main__':unittest.main()
