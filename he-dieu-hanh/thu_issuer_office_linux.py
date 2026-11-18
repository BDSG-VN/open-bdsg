"""Kiểm nguồn Office qua API công khai với hệ tệp Linux thật, dữ liệu tổng hợp."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import thu_phien_office_don_vi as fixtures
from soan_thao_office import SoanThaoOffice


@unittest.skipUnless(sys.platform.startswith('linux'), 'Cần quyền và liên kết hệ tệp Linux thật')
class ThuIssuerOfficeLinux(unittest.TestCase):
    def setUp(self):
        self.case=fixtures.ThuPhienOfficeDonVi()
        self.case.setUp()
        self.addCleanup(self.case.close)
        self.opened=self.case.editor.open(self.case.a,{'id':self.case.file['id']})
        self.path=Path(self.case.tmp.name)/'office-editor-epoch'

    def assert_rejected(self):
        with self.assertRaises(PermissionError):self.case.source(self.opened)
        with self.assertRaises(PermissionError):
            SoanThaoOffice(self.case.app.office,self.case.app.origin)

    def assert_original_source(self):
        self.assertTrue(self.case.source(self.opened).startswith(b'PK'))

    def test_group_and_world_permissions_reject_source_without_rewriting_epoch(self):
        original=self.path.read_bytes()
        for mode in (0o640,0o604,0o660,0o606,0o644):
            with self.subTest(mode=oct(mode)):
                try:
                    self.path.chmod(mode)
                    self.assert_rejected()
                    self.assertEqual(self.path.read_bytes(),original)
                    self.assertEqual(self.path.stat().st_mode&0o777,mode)
                finally:self.path.chmod(0o600)
                self.assert_original_source()

    def test_symlink_rejects_source_and_preserves_original_target(self):
        original=self.path.read_bytes()
        saved=self.path.with_name('epoch-original')
        self.path.rename(saved)
        try:
            self.path.symlink_to(saved.name)
            self.assert_rejected()
            self.assertTrue(self.path.is_symlink())
            self.assertEqual(saved.read_bytes(),original)
        finally:
            self.path.unlink()
            saved.rename(self.path)
        self.assert_original_source()

    def test_directory_is_not_adopted_as_epoch_or_overwritten(self):
        saved=self.path.with_name('epoch-original')
        self.path.rename(saved)
        try:
            self.path.mkdir(mode=0o700)
            self.assert_rejected()
            self.assertTrue(self.path.is_dir())
            self.assertEqual(list(self.path.iterdir()),[])
        finally:
            self.path.rmdir()
            saved.rename(self.path)
        self.assert_original_source()

    def test_second_hardlink_rejects_source_until_link_is_removed(self):
        original=self.path.read_bytes()
        other=self.path.with_name('epoch-hardlink')
        os.link(self.path,other)
        try:
            self.assert_rejected()
            self.assertEqual(self.path.stat().st_nlink,2)
            self.assertEqual(other.read_bytes(),original)
        finally:other.unlink()
        self.assert_original_source()

    def test_path_swap_between_check_and_open_rejects_new_inode_and_symlink(self):
        original=self.path.read_bytes()
        saved=self.path.with_name('epoch-original')
        real_open=os.open
        for kind in ('inode','symlink'):
            with self.subTest(replacement=kind):
                swapped=False
                def swap_before_open(path,flags,*args,**kwargs):
                    nonlocal swapped
                    if (isinstance(path,(str,os.PathLike)) and Path(path)==self.path
                            and (flags&os.O_ACCMODE)==os.O_RDONLY and not flags&os.O_CREAT and not swapped):
                        swapped=True
                        self.path.rename(saved)
                        try:
                            if kind=='inode':
                                self.path.write_bytes(original)
                                self.path.chmod(0o600)
                            else:self.path.symlink_to(saved.name)
                            self.assertEqual(self.path.is_symlink(),kind=='symlink')
                            return real_open(path,flags,*args,**kwargs)
                        finally:
                            # Trả đường dẫn gốc trước các lần kiểm kế tiếp;
                            # phép thử phải bắt được tráo tạm thời ở lần đọc này.
                            self.path.unlink(missing_ok=True)
                            saved.rename(self.path)
                    return real_open(path,flags,*args,**kwargs)
                # Chỉ chèn lịch đổi tệp ở biên IO; lstat/open/fstat thật
                # phân biệt inode mới và symlink trỏ về chính inode cũ.
                with patch('phien_office_don_vi.os.open',side_effect=swap_before_open):
                    with self.assertRaises(PermissionError):self.case.source(self.opened)
                self.assertTrue(swapped)
                self.assertEqual(self.path.read_bytes(),original)
                self.assertFalse(self.path.is_symlink())
                self.assert_original_source()


if __name__=='__main__':unittest.main()
