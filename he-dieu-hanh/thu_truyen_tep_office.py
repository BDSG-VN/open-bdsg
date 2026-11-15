"""Tệp tổng hợp: truyền theo phần, quyền, reservation, retry và backup."""

import base64
import hashlib
import io
import secrets
import sqlite3
import tempfile
import time
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from kiem_tep_office import LoiDinhDangVanPhong, kiem_tep
from may_chu import UngDung

A = {"id": "operator-a", "role": "operator", "name": "Nguoi A"}
B = {"id": "operator-b", "role": "operator", "name": "Nguoi B"}


def office_fixture(extra=None, rels="<Relationships/>", root="word/document.xml"):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in {
            "[Content_Types].xml": "<Types/>",
            "_rels/.rels": rels,
            root: "<document/>",
            **(extra or {}),
        }.items():
            archive.writestr(name, raw)
    return output.getvalue()


class ThuTruyenTep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = UngDung(self.tmp.name, "https://office.example.test", True)
        for actor in (A, B):
            self.app.kho.tao_agent(actor["id"], actor["name"], "operator")
        self.project = self.call("du_an.tao", {"name": "SYNTHETIC Truyen tep"})
        self.addCleanup(self.close)

    def close(self):
        self.app.tasks.close()
        self.app.core.audit.close()
        self.tmp.cleanup()

    def call(self, name, args, actor=A):
        result = self.app.core.goi(actor, name, args)
        self.assertTrue(result["ok"], result)
        return result["ket_qua"]

    def denied(self, name, args, actor=A):
        result = self.app.core.goi(actor, name, args)
        self.assertFalse(result["ok"], result)

    def begin(self, raw, name="ho-so.txt", key=None):
        return self.call(
            "van_phong.bat_dau_tai",
            {
                "project_id": self.project["id"],
                "name": name,
                "total": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "request_key": key or secrets.token_hex(16),
            },
        )

    def part(self, upload, raw, offset):
        return self.call(
            "van_phong.ghi_phan",
            {
                "id": upload["id"],
                "offset": offset,
                "content_base64": base64.b64encode(raw).decode(),
            },
        )

    def test_eight_mib_roundtrip_idempotency_and_immutable_download(self):
        raw = b"x" * (8 * 1024 * 1024)
        key = secrets.token_hex(16)
        upload = self.begin(raw, key=key)
        self.assertEqual(self.begin(raw, key=key)["id"], upload["id"])
        step = 512 * 1024
        for offset in range(0, len(raw), step):
            self.part(upload, raw[offset : offset + step], offset)
        first = self.call("van_phong.ket_thuc_tai", {"id": upload["id"]})
        again = self.call("van_phong.ket_thuc_tai", {"id": upload["id"]})
        self.assertEqual(first["file"]["id"], again["file"]["id"])
        file = first["file"]
        preview = self.call("van_phong.doc", {"id": file["id"]})
        self.assertIsNone(preview["content_base64"])
        parts = []
        for offset in range(0, len(raw), step):
            value = self.call(
                "van_phong.doc_phan", {"id": file["id"], "version": 1, "offset": offset}
            )
            parts.append(base64.b64decode(value["content_base64"]))
        self.assertEqual(b"".join(parts), raw)
        self.assertEqual(
            len(
                self.call("van_phong.danh_sach", {"project_id": self.project["id"]})[
                    "files"
                ]
            ),
            1,
        )

    def test_retry_part_gap_mismatch_and_incomplete_finish(self):
        upload = self.begin(b"abcdef")
        self.part(upload, b"abc", 0)
        self.assertEqual(self.part(upload, b"abc", 0)["received"], 3)
        self.denied(
            "van_phong.ghi_phan",
            {"id": upload["id"], "offset": 1, "content_base64": "YmM="},
        )
        events = [
            e
            for e in self.app.kho.hoat_dong(A["id"])
            if e["action"] == "office-ghi-phan"
        ]
        self.assertEqual(len(events), 1)
        self.denied(
            "van_phong.ghi_phan",
            {"id": upload["id"], "offset": 0, "content_base64": "eHl6"},
        )
        self.denied(
            "van_phong.ghi_phan",
            {"id": upload["id"], "offset": 4, "content_base64": "ZA=="},
        )
        self.denied("van_phong.ket_thuc_tai", {"id": upload["id"]})
        self.part(upload, b"def", 3)
        self.call("van_phong.ket_thuc_tai", {"id": upload["id"]})

    def test_owner_scope_revoked_project_and_archived_upload(self):
        upload = self.begin(b"abcdef")
        self.call(
            "cong_tac.chia_se",
            {"id": self.project["id"], "identity": B["id"], "role": "editor"},
        )
        for name in ("trang_thai_tai", "huy_tai", "ket_thuc_tai"):
            self.denied("van_phong." + name, {"id": upload["id"]}, B)
        self.assertEqual(
            self.call("van_phong.phien_tai", {"project_id": self.project["id"]}, B)[
                "uploads"
            ],
            [],
        )
        self.call("du_an.luu_tru", {"id": self.project["id"]})
        self.denied(
            "van_phong.ghi_phan",
            {"id": upload["id"], "offset": 0, "content_base64": "YWJj"},
        )
        self.assertTrue(
            self.call("van_phong.huy_tai", {"id": upload["id"]})["cancelled"]
        )

    def test_reservation_counts_quota_and_cancel_releases_it(self):
        self.app.office.MAX_TOTAL_BYTES = 10
        upload = self.begin(b"12345678")
        self.denied(
            "van_phong.tao",
            {
                "project_id": self.project["id"],
                "name": "other.txt",
                "content_base64": "YWJj",
            },
        )
        self.assertEqual(
            self.call("van_phong.trang_thai", {"project_id": self.project["id"]})[
                "transfer_usage"
            ]["reserved_bytes"],
            8,
        )
        self.call("van_phong.huy_tai", {"id": upload["id"]})
        self.call(
            "van_phong.tao",
            {
                "project_id": self.project["id"],
                "name": "other.txt",
                "content_base64": "YWJj",
            },
        )

    def test_global_quota_and_expiration(self):
        self.app.office.MAX_GLOBAL_BYTES = 10
        upload = self.begin(b"12345678")
        self.denied(
            "van_phong.bat_dau_tai",
            {
                "project_id": self.project["id"],
                "name": "b.txt",
                "total": 3,
                "sha256": hashlib.sha256(b"abc").hexdigest(),
                "request_key": secrets.token_hex(16),
            },
        )
        with patch("van_phong.time.time", return_value=time.time() + 1000):
            self.denied("van_phong.trang_thai_tai", {"id": upload["id"]})
            other = self.begin(b"abc")
        self.assertNotEqual(upload["id"], other["id"])

    def test_failed_format_never_publishes_and_cancel_after_finish_is_honest(self):
        bad = self.begin(b"not an office file", "bad.docx")
        self.part(bad, b"not an office file", 0)
        self.denied("van_phong.ket_thuc_tai", {"id": bad["id"]})
        self.assertEqual(
            self.call("van_phong.danh_sach", {"project_id": self.project["id"]})[
                "files"
            ],
            [],
        )
        self.call("van_phong.huy_tai", {"id": bad["id"]})
        good = self.begin(b"")
        result = self.call("van_phong.ket_thuc_tai", {"id": good["id"]})
        self.assertEqual(
            self.call("van_phong.huy_tai", {"id": good["id"]}),
            {"cancelled": False, "completed": True, "file_id": result["file"]["id"]},
        )

    def test_current_permission_is_checked_on_every_download_part(self):
        upload = self.begin(b"abcdef")
        self.part(upload, b"abcdef", 0)
        file = self.call("van_phong.ket_thuc_tai", {"id": upload["id"]})["file"]
        self.call(
            "cong_tac.chia_se",
            {"id": self.project["id"], "identity": B["id"], "role": "viewer"},
        )
        args = {"id": file["id"], "version": 1, "offset": 0}
        self.call("van_phong.doc_phan", args, B)
        self.call(
            "cong_tac.chia_se",
            {"id": self.project["id"], "identity": B["id"], "role": "revoke"},
        )
        self.denied("van_phong.doc_phan", args, B)

    def test_consistent_backup_restores_unfinished_upload_and_large_content(self):
        raw = b"abc" * 200000
        upload = self.begin(raw)
        self.part(upload, raw[:200000], 0)
        folder = Path(self.tmp.name) / "restore"
        folder.mkdir()
        with (
            closing(sqlite3.connect(self.app.kho.db)) as source,
            closing(sqlite3.connect(folder / "van-hanh.db")) as target,
        ):
            source.backup(target)
        restored = UngDung(str(folder), "https://office.example.test", True)
        try:
            result = restored.core.goi(
                A, "van_phong.trang_thai_tai", {"id": upload["id"]}
            )
            self.assertEqual(result["ket_qua"]["received"], 200000)
            result = restored.core.goi(
                A,
                "van_phong.ghi_phan",
                {
                    "id": upload["id"],
                    "offset": 200000,
                    "content_base64": base64.b64encode(raw[200000:]).decode(),
                },
            )
            self.assertTrue(result["ok"], result)
            result = restored.core.goi(
                A, "van_phong.ket_thuc_tai", {"id": upload["id"]}
            )
            self.assertTrue(result["ok"], result)
            value = restored.core.goi(
                A, "van_phong.doc", {"id": result["ket_qua"]["file"]["id"]}
            )["ket_qua"]
            self.assertEqual(value["sha256"], hashlib.sha256(raw).hexdigest())
        finally:
            restored.tasks.close()
            restored.core.audit.close()


class ThuKiemDang(unittest.TestCase):
    def test_content_xml_entities_depth_and_active_declarations_are_rejected(self):
        declaration = '<!DOCTYPE x [<!ENTITY y "x">]><document>&y;</document>'
        variants = [
            office_fixture({"word/document.xml": declaration}),
            office_fixture(
                {
                    "word/document.xml": (
                        '<?xml version="1.0" encoding="UTF-16"?>' + declaration
                    ).encode("utf-16")
                }
            ),
            office_fixture({"word/extra.xml": declaration}),
            office_fixture({"word/document.xml": "<x>" * 129 + "</x>" * 129}),
            office_fixture(
                {
                    "word/a.bin": b"x",
                    "[Content_Types].xml": '<Types><Override ContentType="application/vnd.ms-office.activeX"/></Types>',
                }
            ),
            office_fixture(
                {"word/a.bin": b"x"},
                rels='<Relationships><Relationship Type="http://schemas.example/oleObject"/></Relationships>',
            ),
        ]
        for raw in variants:
            with self.subTest(size=len(raw)), self.assertRaises(LoiDinhDangVanPhong):
                kiem_tep("test.docx", raw)

    def test_large_content_xml_is_checked_without_a_dom(self):
        value = office_fixture(
            {"word/document.xml": "<document><p>" + "x" * 200000 + "</p></document>"}
        )
        self.assertEqual(
            kiem_tep("test.docx", value)["format_state"], "cau-truc-co-ban"
        )

    def test_three_formats_and_external_warning_without_fetch(self):
        for suffix, root in (
            ("docx", "word/document.xml"),
            ("xlsx", "xl/workbook.xml"),
            ("pptx", "ppt/presentation.xml"),
        ):
            result = kiem_tep(
                "test." + suffix,
                office_fixture(
                    root=root,
                    rels='<Relationships><Relationship TargetMode="Exte&#114;nal" Target="https://example.invalid/"/></Relationships>',
                ),
            )
            self.assertEqual(result["virus_state"], "chua-quet")
            self.assertEqual(result["warnings"], ["co-lien-ket-ngoai"])

    def test_invalid_zip_traversal_macros_entities_and_bomb_are_rejected(self):
        values = [
            b"not zip",
            office_fixture({"../x": "x"}),
            office_fixture({"word/vbaProject.bin": b"x"}),
            office_fixture({"word/embeddings/o.bin": b"x"}),
            office_fixture(
                rels='<!DOCTYPE x [<!ENTITY y "x">]><Relationships>&y;</Relationships>'
            ),
            office_fixture({"word/bomb.xml": "x" * 1100000}),
        ]
        for raw in values:
            with self.subTest(size=len(raw)), self.assertRaises(LoiDinhDangVanPhong):
                kiem_tep("test.docx", raw)

    def test_text_and_pdf_signatures_are_not_antivirus(self):
        self.assertEqual(
            kiem_tep("x.txt", "Thanh Hoá".encode())["format_state"], "cau-truc-co-ban"
        )
        self.assertEqual(
            kiem_tep("x.pdf", b"%PDF-1.7\n")["warnings"], ["pdf-chua-kiem-noi-dung"]
        )
        for name, raw in (("x.txt", b"\xff"), ("x.txt", b"\0"), ("x.pdf", b"not pdf")):
            with self.assertRaises(LoiDinhDangVanPhong):
                kiem_tep(name, raw)


if __name__ == "__main__":
    unittest.main()
