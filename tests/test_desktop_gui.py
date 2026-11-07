"""Native widget behavior checks; no interaction with the user's desktop."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
try:
    from PySide6.QtWidgets import QApplication,QDialog
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    QT=True
except ImportError:QT=False

@unittest.skipUnless(QT,'Desktop dependencies are optional in the web-only environment')
class DesktopGUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        from bandtab.desktop.window import MainWindow
        from bandtab import demo
        self.tmp=tempfile.TemporaryDirectory();self.window=MainWindow(Path(self.tmp.name))
        folder=self.window.library.create_folder();self.project=demo.create(folder);self.window.library.save(self.project)
        self.window.open_project(self.project);self.window.show();self.app.processEvents()
    def tearDown(self):
        self.window.close();self.window.deleteLater();self.app.processEvents();self.tmp.cleanup()
    def test_native_controls_and_track_filter(self):
        w=self.window;self.assertEqual(w.table.rowCount(),192)
        w.track.setCurrentIndex(2);self.app.processEvents()
        self.assertEqual(w.canvas.track_id,'bass');self.assertEqual(w.table.rowCount(),32)
        w.zoom.setValue(150);self.assertEqual(w.canvas.scale,150)
        w.review.setChecked(True);self.assertTrue(w.canvas.review_only)
    def test_note_edit_updates_pitch_and_fingering_then_undo(self):
        w=self.window;n=w.project['tracks'][0]['notes'][0];original=n['pitch']
        def finish():
            dialog=self.app.activeModalWidget();dialog.pitch.setValue(42);dialog.submit()
        QTimer.singleShot(20,finish);w.edit_note('guitar',n['id'])
        changed=w.project['tracks'][0]['notes'][0];self.assertEqual(changed['pitch'],42);self.assertEqual((changed['string'],changed['fret']),(6,2))
        self.assertTrue(w.dirty);w.undo();self.assertEqual(w.project['tracks'][0]['notes'][0]['pitch'],original)
        w.save_current();self.assertFalse(w.dirty)
    def test_mixer_has_single_source_mode_and_saved_edit(self):
        w=self.window;w.mix_value('guitar','solo',True)
        self.assertTrue(w.transport.stem_mode);self.assertEqual(w.transport.outputs[0].volume(),0)
        self.assertGreater(w.transport.outputs[1].volume(),0);self.assertEqual(w.transport.outputs[2].volume(),0)
        w.snapshot();w.project['tracks'][0]['notes'][0]['review']=True;w.changed();w.save_current()
        self.assertTrue(w.library.load(w.project['id'])['tracks'][0]['notes'][0]['review'])
    def test_invalid_note_time_does_not_accept_dialog(self):
        from bandtab.desktop.dialogs import NoteDialog
        d=NoteDialog(self.project['tracks'][0],self.project['tracks'][0]['notes'][0],self.project['duration'])
        d.start.setValue(1);d.end.setValue(.5);d.submit()
        self.assertNotEqual(d.result(),QDialog.DialogCode.Accepted);self.assertTrue(d.error.text())
        d.deleteLater()

if __name__=='__main__':unittest.main()
