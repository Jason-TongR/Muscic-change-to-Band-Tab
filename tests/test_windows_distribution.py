"""Distribution contracts that can be checked before the native Windows run."""
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from bandtab.runtime import ensure_model,process_options
from scripts.build_desktop import checksums,find_inno
from scripts.check_windows_release import assert_x64_executable,isolated_environment


class WindowsDistributionTests(unittest.TestCase):
    def test_offline_mode_fails_without_attempting_a_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.dict(os.environ,{'BANDTAB_OFFLINE':'1','BANDTAB_MODEL_HOME':str(root/'cache')}), \
                 patch('bandtab.runtime.resources',return_value=root), \
                 patch('urllib.request.urlopen') as network:
                with self.assertRaises(FileNotFoundError):ensure_model()
                network.assert_not_called()
    def test_windows_workers_do_not_open_console_windows(self):
        with patch('bandtab.runtime.os.name','nt'):
            self.assertEqual(process_options(),{'creationflags':0x08000000})
    def test_clean_execution_cannot_import_from_build_environment(self):
        with patch.dict(os.environ,{'SystemRoot':'C:/Windows','PYTHONPATH':'build-packages',
                'PYTHONHOME':'python-install','BANDTAB_MODEL_HOME':'build-models','VIRTUAL_ENV':'builder'}):
            env=isolated_environment(Path('C:/test library'))
        for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','BANDTAB_MODEL_HOME'):
            self.assertNotIn(key,env)
        self.assertNotIn('builder',env['PATH'])
        self.assertEqual(env['BANDTAB_OFFLINE'],'1')
        self.assertEqual(env['QT_QPA_PLATFORM'],'windows')
    def test_rejects_a_renamed_linux_binary_and_32bit_windows_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'application.exe'
            file.write_bytes(b'\x7fELF'+bytes(100))
            with self.assertRaises(ValueError):assert_x64_executable(file)
            data=bytearray(128);data[:2]=b'MZ';struct.pack_into('<I',data,0x3c,64)
            data[64:68]=b'PE\0\0';struct.pack_into('<H',data,68,0x14c);file.write_bytes(data)
            with self.assertRaises(ValueError):assert_x64_executable(file)
            struct.pack_into('<H',data,68,0x8664);file.write_bytes(data)
            assert_x64_executable(file)
    def test_checksums_cover_the_program_and_shareable_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'portable.zip').write_bytes(b'package')
            (root/'原创练习曲.bandtab').write_bytes(b'example')
            (root/'old-report.json').write_text('{}')
            result=checksums(root)
            self.assertEqual(set(result),{'portable.zip','原创练习曲.bandtab'})
            self.assertEqual(result['portable.zip'],hashlib.sha256(b'package').hexdigest())
            self.assertEqual(json.loads((root/'SHA256SUMS.json').read_text(encoding='utf8')),result)
    def test_explicit_compiler_path_supports_spaces(self):
        with tempfile.TemporaryDirectory(prefix='Inno Setup ') as tmp:
            compiler=Path(tmp)/'ISCC.exe';compiler.touch()
            with patch.dict(os.environ,{'ISCC':str(compiler)}):
                self.assertEqual(find_inno(),compiler)


if __name__=='__main__':unittest.main()
