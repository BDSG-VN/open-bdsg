"""Tái hiện lỗi vận hành qua công cụ thật, dùng kho tổng hợp và tài khoản riêng."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from may_chu import UngDung

OWNER = {"id": "chu-quan", "name": "Chủ kiểm thử", "role": "quan-tri"}


@unittest.skipUnless(
    os.environ.get("BDSG_TEST_RUNTIME") == "1", "Cần Linux non-root có runtime cách ly"
)
class ThuKhoiPhucRuntime(unittest.TestCase):
    def test_restart_releases_running_python_without_losing_previous_results(self):
        with tempfile.TemporaryDirectory() as folder:
            program = r"""
import json,os,sys,threading,time
from pathlib import Path
os.environ['TMPDIR']=sys.argv[1]
sys.path.insert(0,sys.argv[2])
from may_chu import UngDung
actor={'id':'chu-quan','name':'Test','role':'quan-tri'}
app=UngDung(sys.argv[1],'https://thanhhoa.bdsg.vn',True)
app.kho.tao_chu('synthetic-owner-password-only')
def tool(name,args):
 r=app.core.goi(actor,name,args)
 if not r['ok']:raise RuntimeError(r)
 return r['ket_qua']
job=tool('cong_viec.tao',{'prompt':'Kiem thu khoi phuc khi Python bi gian doan','allow_python':True,'template':'de-xuat-giai-phap'})
for _ in range(100):
 task=tool('cong_viec.chi_tiet',{'id':job['id']})
 if task['status']=='completed':break
 time.sleep(.01)
before=[a['id'] for a in task['artifacts']]
threading.Thread(target=lambda:tool('runtime.python',{'task_id':job['id'],'code':'import os\nos.write(2, b"BDSG_RUNTIME_STARTED")\nwhile True: pass'}),daemon=True).start()
for _ in range(400):
 task=tool('cong_viec.chi_tiet',{'id':job['id']})
 started=any(b'BDSG_RUNTIME_STARTED' in p.read_bytes() for p in Path(sys.argv[1]).glob('bdsg-result-*/stderr'))
 if task.get('runtime_running') and started:
  print(json.dumps({'task_id':job['id'],'before':before}),flush=True)
  os._exit(0)
 time.sleep(.01)
os._exit(2)
"""
            r = subprocess.run(
                [sys.executable, "-c", program, folder, str(Path(__file__).parent)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            crashed = json.loads(r.stdout)
            app = UngDung(folder, "https://thanhhoa.bdsg.vn", True)
            try:
                restored = app.core.goi(
                    OWNER, "cong_viec.chi_tiet", {"id": crashed["task_id"]}
                )
                self.assertTrue(restored["ok"], restored)
                task = restored["ket_qua"]
                self.assertFalse(
                    task.get("runtime_running"),
                    "Sau restart không được giữ cờ Python đang chạy của tiến trình đã chết",
                )
                self.assertEqual(
                    [a["id"] for a in task["artifacts"]], crashed["before"]
                )
                continued = app.core.goi(
                    OWNER,
                    "cong_viec.tiep_tuc",
                    {
                        "id": task["id"],
                        "text": "Tiep tuc tu ket qua da luu, khong tu chay lai ma cu",
                    },
                )
                self.assertTrue(continued["ok"], continued)
            finally:
                app.schedules.close()
                app.tasks.close()
                app.core.audit.close()


@unittest.skipUnless(
    os.environ.get("BDSG_TEST_RUNTIME") == "1", "Cần Linux non-root có runtime cách ly"
)
class ThuHanMucKetQua(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = UngDung(self.temp.name, "https://thanhhoa.bdsg.vn", True)
        self.app.kho.tao_chu("synthetic-owner-password-only")
        self.addCleanup(self.close)
        job = self.tool(
            "cong_viec.tao",
            {"prompt": "Kiem han muc dau ra duoc luu thuc te", "allow_python": True, "template": "de-xuat-giai-phap"},
        )
        self.identifier = job["id"]
        for _ in range(100):
            if self.detail()["status"] == "completed":
                break
            time.sleep(0.01)

    def close(self):
        self.app.schedules.close()
        self.app.tasks.close()
        self.app.core.audit.close()
        self.temp.cleanup()

    def tool(self, name, args):
        r = self.app.core.goi(OWNER, name, args)
        self.assertTrue(r["ok"], r)
        return r["ket_qua"]

    def detail(self):
        return self.tool("cong_viec.chi_tiet", {"id": self.identifier})

    def add_files(self, count, size=1):
        names = ["o" + str(i) + ".txt" for i in range(count)]
        return self.app.core.goi(
            OWNER,
            "runtime.python",
            {
                "task_id": self.identifier,
                "output_names": names,
                "code": "for n in "
                + repr(names)
                + ':\n open(n,"w").write("x"*'
                + str(size)
                + ")",
            },
        )

    def test_batch_cannot_cross_file_count_budget(self):
        for count in [8] * 9 + [6]:
            r = self.add_files(count)
            self.assertTrue(r["ok"], r)
            self.assertTrue(r["ket_qua"]["ok"], r)
        before = self.detail()["artifacts"]
        self.assertEqual(len(before), 79)
        result = self.add_files(8)
        self.assertFalse(result["ok"], "Không được lưu cả lô khiến số tệp vượt 80")
        after = self.detail()
        self.assertEqual(
            [a["id"] for a in after["artifacts"]], [a["id"] for a in before]
        )
        self.assertFalse(after.get("runtime_running"))

    def test_batch_cannot_cross_byte_budget(self):
        for _ in range(16):
            r = self.add_files(2, 250000)
            self.assertTrue(r["ok"], r)
            self.assertTrue(r["ket_qua"]["ok"], r)
        before = self.detail()["artifacts"]
        self.assertLess(
            sum(len(a["content"].encode()) for a in before), 8 * 1024 * 1024
        )
        result = self.add_files(2, 250000)
        self.assertFalse(
            result["ok"], "Không được lưu cả lô khiến dung lượng vượt 8 MiB"
        )
        self.assertEqual(
            [a["id"] for a in self.detail()["artifacts"]], [a["id"] for a in before]
        )


if __name__ == "__main__":
    unittest.main()
