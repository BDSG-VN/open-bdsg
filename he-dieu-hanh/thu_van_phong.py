"""Kiểm kho Office qua nhân: quyền, xung đột và lịch sử bằng dữ liệu tạm."""

import base64
import concurrent.futures
import tempfile
import threading
import unittest

from may_chu import UngDung
from van_phong import VanPhong

A = {"id": "operator-a", "role": "operator", "name": "Nguoi A"}
B = {"id": "operator-b", "role": "operator", "name": "Nguoi B"}
OWNER = {"id": "chu-quan", "role": "quan-tri", "name": "Chu quan"}
AGENT = {"id": "agent-a", "role": "agent", "name": "Agent"}


def encoded(value):
    return base64.b64encode(value.encode()).decode()


class ThuVanPhong(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = UngDung(self.tmp.name, "https://office.example.test", True)
        self.app.kho.tao_chu("chi-dung-cho-kiem-thu")
        for actor in (A, B, AGENT):
            self.app.kho.tao_agent(actor["id"], actor["name"], actor["role"])
        self.addCleanup(self.close)
        self.project = self.call(A, "du_an.tao", {"name": "Du an Office thu"})

    def close(self):
        self.app.tasks.close()
        self.app.core.audit.close()
        self.tmp.cleanup()

    def call(self, actor, name, args):
        result = self.app.core.goi(actor, name, args)
        self.assertTrue(result["ok"], result)
        return result["ket_qua"]

    def denied(self, actor, name, args):
        result = self.app.core.goi(actor, name, args)
        self.assertFalse(result["ok"], result)

    def create(self, name="ke-hoach.txt", value="Ban dau"):
        return self.call(
            A,
            "van_phong.tao",
            {
                "project_id": self.project["id"],
                "name": name,
                "content_base64": encoded(value),
            },
        )

    def update(self, file, action, **args):
        return self.call(
            A,
            "van_phong.cap_nhat",
            {
                "id": file["id"],
                "expected_revision": file["revision"],
                "action": action,
                **args,
            },
        )

    def share(self, role):
        return self.call(
            A,
            "cong_tac.chia_se",
            {
                "id": self.project["id"],
                "identity": B["id"],
                "role": role,
            },
        )

    def test_roundtrip_restart_and_truthful_editor_status(self):
        file = self.create(value="Kế hoạch Thanh Hoá")
        for office in (self.app.office, VanPhong(self.app.kho, self.app.projects)):
            result = office.read(A, {"id": file["id"]})
            self.assertEqual(
                base64.b64decode(result["content_base64"]).decode(),
                "Kế hoạch Thanh Hoá",
            )
        result = self.call(
            A, "van_phong.trang_thai", {"project_id": self.project["id"]}
        )
        self.assertEqual(result["editor_state"], "chua-cau-hinh")
        self.assertEqual(result["google_state"], "chua-ket-noi")
        self.assertEqual(file["scan_state"], "chua-quet")

    def test_no_cross_project_access_and_no_automatic_agent_grant(self):
        file = self.create()
        for actor in (B, AGENT):
            self.denied(actor, "van_phong.doc", {"id": file["id"]})
            self.denied(actor, "van_phong.lich_su", {"id": file["id"]})
            self.denied(
                actor, "van_phong.danh_sach", {"project_id": self.project["id"]}
            )
        self.assertEqual(
            self.call(OWNER, "van_phong.doc", {"id": file["id"]})["version"], 1
        )

    def test_viewer_editor_and_revocation_apply_to_old_file_ids(self):
        file = self.create()
        self.share("viewer")
        self.call(B, "van_phong.doc", {"id": file["id"]})
        args = {
            "id": file["id"],
            "expected_revision": 1,
            "action": "save",
            "content_base64": encoded("Moi"),
        }
        self.denied(B, "van_phong.cap_nhat", args)
        self.share("editor")
        self.call(B, "van_phong.cap_nhat", args)
        self.share("revoke")
        self.denied(B, "van_phong.doc", {"id": file["id"], "version": 1})

    def test_revisions_restore_old_content_without_destroying_history(self):
        first = self.create()
        second = self.update(first, "save", content_base64=encoded("Ban moi"))
        self.denied(
            A,
            "van_phong.cap_nhat",
            {
                "id": first["id"],
                "expected_revision": 1,
                "action": "save",
                "content_base64": encoded("Ghi de"),
            },
        )
        restored = self.update(second, "restore-version", version=1)
        self.assertEqual(restored["version"], 3)
        history = self.call(A, "van_phong.lich_su", {"id": first["id"]})
        self.assertEqual([r["version"] for r in history["versions"]], [3, 2, 1])
        result = self.call(A, "van_phong.doc", {"id": first["id"], "version": 2})
        self.assertEqual(base64.b64decode(result["content_base64"]), b"Ban moi")
        result = self.call(A, "van_phong.doc", {"id": first["id"]})
        self.assertEqual(base64.b64decode(result["content_base64"]), b"Ban dau")

    def test_two_writers_cannot_silently_overwrite(self):
        file = self.create()
        barrier = threading.Barrier(2)

        def save(value):
            barrier.wait(timeout=5)
            return self.app.core.goi(
                A,
                "van_phong.cap_nhat",
                {
                    "id": file["id"],
                    "expected_revision": 1,
                    "action": "save",
                    "content_base64": encoded(value),
                },
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(save, value) for value in ("Nguoi mot", "Nguoi hai")
            ]
            results = [f.result(timeout=10) for f in futures]
        self.assertEqual(sum(r["ok"] for r in results), 1)
        self.assertEqual(
            len(self.call(A, "van_phong.lich_su", {"id": file["id"]})["versions"]), 2
        )

    def test_trash_restore_rename_and_archive(self):
        file = self.create()
        renamed = self.update(file, "rename", name="ten-moi.txt")
        trashed = self.update(renamed, "trash")
        pid = {"project_id": self.project["id"]}
        self.assertEqual(self.call(A, "van_phong.danh_sach", pid)["files"], [])
        self.assertEqual(
            len(self.call(A, "van_phong.danh_sach", {**pid, "trashed": True})["files"]),
            1,
        )
        self.denied(
            A,
            "van_phong.cap_nhat",
            {
                "id": file["id"],
                "expected_revision": 3,
                "action": "save",
                "content_base64": encoded("x"),
            },
        )
        restored = self.update(trashed, "untrash")
        self.assertEqual(restored["name"], "ten-moi.txt")
        self.call(A, "du_an.luu_tru", {"id": self.project["id"]})
        self.denied(
            A,
            "van_phong.cap_nhat",
            {"id": file["id"], "expected_revision": 4, "action": "trash"},
        )
        self.call(A, "van_phong.doc", {"id": file["id"]})

    def test_invalid_payloads_are_rejected_and_empty_files_are_valid(self):
        for name, content in (
            ("../x.txt", ""),
            ("x.html", ""),
            ("x.txt", "%%%"),
            ("x.txt", "a" * 50000),
        ):
            self.denied(
                A,
                "van_phong.tao",
                {
                    "project_id": self.project["id"],
                    "name": name,
                    "content_base64": content,
                },
            )
        file = self.create(value="")
        self.assertEqual(self.call(A, "van_phong.doc", {"id": file["id"]})["size"], 0)
        self.denied(
            A,
            "van_phong.cap_nhat",
            {"id": file["id"], "expected_revision": True, "action": "trash"},
        )
        self.denied(
            A,
            "van_phong.cap_nhat",
            {
                "id": file["id"],
                "expected_revision": 1,
                "action": "rename",
                "name": "converted.xlsx",
            },
        )

    def test_quota_failure_is_atomic_and_trash_does_not_reset_quota(self):
        self.app.office.MAX_FILES = 1
        self.app.office.MAX_TOTAL_BYTES = 10
        file = self.create()
        self.denied(
            A,
            "van_phong.cap_nhat",
            {
                "id": file["id"],
                "expected_revision": 1,
                "action": "save",
                "content_base64": encoded("0123456789"),
            },
        )
        self.assertEqual(
            self.call(A, "van_phong.doc", {"id": file["id"]})["version"], 1
        )
        self.assertEqual(
            len(self.call(A, "van_phong.lich_su", {"id": file["id"]})["versions"]), 1
        )
        self.update(file, "trash")
        self.denied(
            A,
            "van_phong.tao",
            {
                "project_id": self.project["id"],
                "name": "other.txt",
                "content_base64": "",
            },
        )

    def test_revoked_identity_and_write_gate(self):
        file = self.create()
        self.app.core.nhan.chinh_sach.cong_ghi.dong()
        self.denied(
            A,
            "van_phong.cap_nhat",
            {"id": file["id"], "expected_revision": 1, "action": "trash"},
        )
        self.call(A, "van_phong.doc", {"id": file["id"]})
        self.app.kho.thu_hoi_agent(A["id"])
        self.denied(A, "van_phong.doc", {"id": file["id"]})

    def test_revocation_after_precheck_never_commits_content(self):
        file = self.create()
        verify = self.app.core.verify_actor
        revoked = False

        def revoke_after_first_check(actor):
            nonlocal revoked
            valid = verify(actor)
            if actor["id"] == A["id"] and not revoked:
                revoked = True
                self.app.kho.thu_hoi_agent(A["id"])
            return valid

        # Chèn sự cố giữa lần xác thực ban đầu và giao dịch, không giả dữ liệu DB.
        self.app.core.verify_actor = revoke_after_first_check
        try:
            self.denied(
                A,
                "van_phong.cap_nhat",
                {
                    "id": file["id"],
                    "expected_revision": 1,
                    "action": "save",
                    "content_base64": encoded("Khong duoc luu"),
                },
            )
        finally:
            self.app.core.verify_actor = verify
        result = self.call(OWNER, "van_phong.doc", {"id": file["id"]})
        self.assertEqual(result["version"], 1)
        self.assertEqual(base64.b64decode(result["content_base64"]), b"Ban dau")


if __name__ == "__main__":
    unittest.main()
