"""Kiểm cấu trúc có giới hạn; không phải bộ quét virus hoặc trình chuyển đổi."""

import io
import struct
import zipfile
import zlib
from pathlib import PurePosixPath
from xml.parsers import expat


class LoiDinhDangVanPhong(ValueError):
    """Tệp không đáp ứng điều kiện nhận của kho Office."""


def _kiem_xml(archive, item, result, budget):
    if item.file_size > 16 * 1024 * 1024:
        raise ValueError("xml-size")
    parser = expat.ParserCreate(namespace_separator="}")
    depth = 0

    def reject(*_args):
        raise ValueError("xml-declaration")

    def start(_name, attributes):
        nonlocal depth
        depth += 1
        budget[0] += 1
        if depth > 128 or budget[0] > 1000000:
            raise ValueError("xml-complexity")
        content_type = attributes.get("ContentType", "").lower()
        relationship = attributes.get("Type", "").lower()
        if any(
            token in content_type or token in relationship
            for token in ("macroenabled", "vbaproject", "activex", "oleobject")
        ) or relationship.endswith("/package"):
            raise ValueError("active-declaration")
        if (
            attributes.get("TargetMode", "").lower() == "external"
            and "co-lien-ket-ngoai" not in result["warnings"]
        ):
            result["warnings"].append("co-lien-ket-ngoai")

    def end(_name):
        nonlocal depth
        depth -= 1

    # Callback chặn ngay ở khai báo, kể cả XML UTF-16; không xây DOM hay tải URL.
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    consumed = 0
    with archive.open(item) as source:
        while data := source.read(65536):
            consumed += len(data)
            if consumed > 16 * 1024 * 1024:
                raise ValueError("xml-size")
            parser.Parse(data, False)
    parser.Parse(b"", True)


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
                    or any(ord(c) < 32 for c in item.orig_filename)
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
            budget = [0]
            for item in items:
                if item.filename.lower().endswith((".xml", ".rels")):
                    _kiem_xml(archive, item, result, budget)
    except (
        ValueError,
        UnicodeError,
        zipfile.BadZipFile,
        OSError,
        RuntimeError,
        expat.ExpatError,
        struct.error,
        zlib.error,
    ):
        raise LoiDinhDangVanPhong(
            "Gói Office lỗi, quá lớn hoặc có nội dung chủ động chưa hỗ trợ"
        ) from None
    return result
