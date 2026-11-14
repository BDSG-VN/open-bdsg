"""Kiểm quyền, ngữ cảnh và lưu trữ có thể khôi phục qua giao diện dự án."""
import tempfile
import unittest
from kho import Kho
from du_an import DuAn

A = {"id": "operator-a", "role": "operator"}
B = {"id": "operator-b", "role": "operator"}
OWNER = {"id": "chu-quan", "role": "quan-tri"}


class ThuDuAn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.kho = Kho(self.tmp.name)
        self.projects = DuAn(self.kho)
        self.data = {"name": "Du an thu nghiem", "instructions": "Chi doc du lieu duoc cap quyen", "context": "Ngu canh rieng khong cong khai"}

    def test_ownership_and_admin_scope(self):
        project = self.projects.create(A, self.data)
        self.assertEqual(len(self.projects.list(A)["projects"]), 1)
        self.assertEqual(self.projects.list(B)["projects"], [])
        self.assertEqual(len(self.projects.list(OWNER)["projects"]), 1)
        with self.assertRaises(ValueError): self.projects.context_for(B, project["id"])
        with self.assertRaises(ValueError): self.projects.update(B, {**self.data, "id": project["id"]})
        with self.assertRaises(PermissionError): self.projects.list({"id":"agent-a","role":"agent"})

    def test_context_snapshot_and_restart(self):
        project = self.projects.create(A, self.data)
        snapshot = self.projects.context_for(A, project["id"])
        self.projects.update(A, {**self.data, "id":project["id"], "context":"Ngu canh moi"})
        self.assertEqual(snapshot["context"], self.data["context"])
        self.assertEqual(DuAn(self.kho).context_for(A,project["id"])["context"], "Ngu canh moi")

    def test_archive_restore_without_data_loss(self):
        project = self.projects.create(A,self.data)
        self.projects.archive(A,project["id"])
        with self.assertRaises(ValueError): self.projects.context_for(A,project["id"])
        self.assertTrue(self.projects.list(A)["projects"][0]["archived"])
        restored=self.projects.archive(A,project["id"],False)
        self.assertFalse(restored["archived"])
        self.assertEqual(restored["context"],self.data["context"])

    def test_limits_and_audit_does_not_copy_context(self):
        for data in [{**self.data,"name":"x"},{**self.data,"context":"x"*12001},{**self.data,"instructions":[]}]:
            with self.assertRaises(ValueError): self.projects.create(A,data)
        self.projects.create(A,self.data)
        events=self.kho.hoat_dong(A["id"])
        self.assertEqual(events[0]["action"],"tao-du-an")
        self.assertNotIn(self.data["context"],str(events))


if __name__ == "__main__":
    unittest.main()
