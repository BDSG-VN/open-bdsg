"""Đầu vào CLI không được bị tính là phép đo đỏ hoặc chạm trình duyệt/dữ liệu thật."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT=pathlib.Path(__file__).with_name('v29_thu_office_ws.py')


class ThuOfficeWSProbe(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
        self.output=self.root/'output'

    def run_probe(self,extra=()):
        return subprocess.run([sys.executable,'-X','utf8',str(SCRIPT),
            '--origin','https://office-qa.example','--bundle-dir',str(self.root),
            '--output-dir',str(self.output),*extra],capture_output=True,encoding='utf-8',timeout=10)

    def bundle(self,*,synthetic=True,mismatched=False):
        key='bdsg-'+'a'*32
        def opened(actor):
            return {'key':key,'config':{'documentType':'word','editorConfig':{'user':{'id':actor}},
                    'document':{'key':'wrong-sdk-key' if mismatched else key}}}
        files={'credentials.json':{'root':'synthetic-only','a':'synthetic-only','c':'synthetic-only'},
               'fixtures.json':{'synthetic':synthetic,'source_commit':'a'*40,
                   'actors':{'owner':'owner','a':'a','c':'c'},'a':opened('a'),'c':opened('c')}}
        for name,data in files.items():
            path=self.root/name;path.write_text(json.dumps(data),encoding='utf-8');path.chmod(0o600)

    def test_unknown_argument_is_setup_error_and_does_not_echo_secret(self):
        result=self.run_probe(('--token','synthetic-redaction-marker'))
        self.assertEqual(result.returncode,3)
        self.assertNotIn('synthetic-redaction-marker',result.stdout+result.stderr)
        self.assertFalse(self.output.exists())

    def test_mismatched_sdk_key_is_rejected_before_browser_or_output(self):
        self.bundle(mismatched=True)
        result=self.run_probe()
        self.assertEqual(result.returncode,3)
        self.assertFalse(self.output.exists())

    def test_unmarked_bundle_cannot_run_membership_revocation(self):
        self.bundle(synthetic=False)
        result=self.run_probe()
        self.assertEqual(result.returncode,3)
        self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
