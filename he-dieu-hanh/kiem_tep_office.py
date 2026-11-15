"""Kiểm cấu trúc có giới hạn; không phải bộ quét virus hoặc trình chuyển đổi."""

import io
import re
import struct
import zipfile
import zlib
from pathlib import PurePosixPath
from xml.etree import ElementTree


class LoiDinhDangVanPhong(ValueError):
    """Tệp không đáp ứng điều kiện nhận của kho Office."""


def kiem_tep(name, raw):
    suffix = PurePosixPath(name).suffix.lower()
    result = {
        "format_state": "cau-truc-co-ban",
        "virus_state": "chua-quet",
        "warnings": [],
    }
    if suffix in (".txt", ".md", ".csv"):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise LoiDinhDangVanPhong("Văn bản phải dùng UTF-8") from None
        if "\0" in text:
            raise LoiDinhDangVanPhong("Văn bản có byte NUL")
        return result
    if suffix == ".pdf":
        if not raw.startswith(b"%PDF-"):
            raise LoiDinhDangVanPhong("Không có chữ ký PDF")
        result["warnings"] = ["pdf-chua-kiem-noi-dung"]
        return result
    roots = {
        ".docx": "word/document.xml",
        ".xlsx": "xl/workbook.xml",
        ".pptx": "ppt/presentation.xml",
    }
    if suffix not in roots:
        raise LoiDinhDangVanPhong("Định dạng chưa hỗ trợ")
    try:
        # Chặn directory khổng lồ trước ZipFile: thư viện đọc cả directory vào RAM.
        end = raw.rfind(b"PK\x05\x06", max(0, len(raw) - 65557))
        if end < 0 or end + 22 > len(raw):
            raise ValueError("zip")
        _, disk, directory_disk, entries_disk, entries, length, offset, comment = (
            struct.unpack_from("<4s4H2LH", raw, end)
        )
        if (
            disk
            or directory_disk
            or entries != entries_disk
            or entries > 2000
            or length > 262144
            or offset + length != end
            or end + 22 + comment != len(raw)
        ):
            raise ValueError("directory")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            items = archive.infolist()
            if len(items) > 2000 or sum(i.file_size for i in items) > 64 * 1024 * 1024:
                raise ValueError("size")
            names = set()
            for item in items:
                path = PurePosixPath(item.filename)
                if (
                    item.filename in names
                    or path.is_absolute()
                    or ".." in path.parts
                    or "\\" in item.filename
                    or len(item.filename) > 512
                ):
                    raise ValueError("path")
                names.add(item.filename)
                low = item.filename.lower()
                if item.flag_bits & 1 or item.compress_type not in (
                    zipfile.ZIP_STORED,
                    zipfile.ZIP_DEFLATED,
                ):
                    raise ValueError("encoding")
                if item.file_size > max(1048576, item.compress_size * 200):
                    raise ValueError("ratio")
                if any(
                    token in low
                    for token in ("vbaproject", "/activex/", "/embeddings/")
                ) or low.endswith((".exe", ".dll", ".com", ".js", ".vbs")):
                    raise ValueError("active")
            if not {"[Content_Types].xml", "_rels/.rels", roots[suffix]} <= names:
                raise ValueError("structure")
            if archive.testzip() is not None:
                raise ValueError("crc")
            for item in items:
                if (
                    item.filename != "[Content_Types].xml"
                    and not item.filename.endswith(".rels")
                ):
                    continue
                if item.file_size > 131072:
                    raise ValueError("xml-size")
                with archive.open(item) as source:
                    xml = source.read(131073).decode("utf-8-sig")
                if (
                    len(xml) > 131072
                    or "\0" in xml
                    or re.search(r"<!\s*(DOCTYPE|ENTITY)", xml, re.IGNORECASE)
                ):
                    raise ValueError("xml")
                tree = ElementTree.fromstring(xml)
                for node in tree.iter():
                    if "macroenabled" in node.attrib.get("ContentType", "").lower():
                        raise ValueError("macro")
                    if (
                        node.attrib.get("TargetMode", "").lower() == "external"
                        and "co-lien-ket-ngoai" not in result["warnings"]
                    ):
                        result["warnings"].append("co-lien-ket-ngoai")
    except (
        ValueError,
        UnicodeError,
        zipfile.BadZipFile,
        OSError,
        RuntimeError,
        ElementTree.ParseError,
        struct.error,
        zlib.error,
    ):
        raise LoiDinhDangVanPhong(
            "Gói Office lỗi, quá lớn hoặc có nội dung chủ động chưa hỗ trợ"
        ) from None
    return result
