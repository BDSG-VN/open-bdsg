"""Tài liệu OOXML trắng do BDSG tạo, không chứa macro hoặc tài nguyên ngoài."""

import io
import zipfile


def create(extension):
    ns = "http://schemas.openxmlformats.org/"
    rel = ns + "package/2006/relationships"
    office = ns + "officeDocument/2006/relationships"
    mime = "application/vnd.openxmlformats-officedocument."
    definitions = {
        "docx": (
            "word/document.xml",
            "wordprocessingml.document.main+xml",
            f'<w:document xmlns:w="{ns}wordprocessingml/2006/main"><w:body><w:p/><w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>',
        ),
        "xlsx": (
            "xl/workbook.xml",
            "spreadsheetml.sheet.main+xml",
            f'<workbook xmlns="{ns}spreadsheetml/2006/main" xmlns:r="{office}"><sheets><sheet name="Trang 1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        ),
        "pptx": (
            "ppt/presentation.xml",
            "presentationml.presentation.main+xml",
            f'<p:presentation xmlns:p="{ns}presentationml/2006/main" xmlns:r="{office}"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst><p:sldSz cx="12192000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>',
        ),
    }
    if extension not in definitions:
        raise ValueError("Chọn docx, xlsx hoặc pptx")
    main, content_type, content = definitions[extension]
    files = {
        main: content,
        "_rels/.rels": f'<Relationships xmlns="{rel}"><Relationship Id="rId1" Type="{office}/officeDocument" Target="{main}"/></Relationships>',
    }
    overrides = [(main, mime + content_type)]
    if extension == "xlsx":
        files["xl/_rels/workbook.xml.rels"] = (
            f'<Relationships xmlns="{rel}"><Relationship Id="rId1" Type="{office}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
        )
        files["xl/worksheets/sheet1.xml"] = (
            f'<worksheet xmlns="{ns}spreadsheetml/2006/main"><sheetData/></worksheet>'
        )
        overrides.append(
            ("xl/worksheets/sheet1.xml", mime + "spreadsheetml.worksheet+xml")
        )
    if extension == "pptx":
        files["ppt/_rels/presentation.xml.rels"] = (
            f'<Relationships xmlns="{rel}"><Relationship Id="rId1" Type="{office}/slide" Target="slides/slide1.xml"/></Relationships>'
        )
        files["ppt/slides/slide1.xml"] = (
            f'<p:sld xmlns:p="{ns}presentationml/2006/main" xmlns:a="{ns}drawingml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
        )
        overrides.append(("ppt/slides/slide1.xml", mime + "presentationml.slide+xml"))
    if extension == "pptx":
        extra_files, extra_overrides = _presentation(ns, office, rel)
        files.update(extra_files)
        overrides.extend((path, mime + kind) for path, kind in extra_overrides)
    files["[Content_Types].xml"] = (
        '<Types xmlns="'
        + ns
        + 'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
        + "".join(
            f'<Override PartName="/{path}" ContentType="{kind}"/>'
            for path, kind in overrides
        )
        + "</Types>"
    )
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, value in files.items():
            # ZIP metadata cố định để retry tạo mẫu có cùng dấu kiểm; ngày
            # người dùng tạo tài liệu được lưu riêng trong kho phiên bản.
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(
                info, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + value
            )
    return result.getvalue()


def _presentation(ns, office, rel):
    """Slide cần layout/master/theme, kể cả khi chỉ có một trang trắng."""
    drawing = ns + "drawingml/2006/main"
    presentation = ns + "presentationml/2006/main"
    namespaces = f'xmlns:p="{presentation}" xmlns:a="{drawing}" xmlns:r="{office}"'
    group = '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
    relationships = lambda values: (
        f'<Relationships xmlns="{rel}">'
        + "".join(
            f'<Relationship Id="{identifier}" Type="{office}/{kind}" Target="{target}"/>'
            for identifier, kind, target in values
        )
        + "</Relationships>"
    )
    files = {
        "ppt/presentation.xml": f'<p:presentation {namespaces}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId2"/></p:sldMasterIdLst><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst><p:sldSz cx="12192000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>',
        "ppt/_rels/presentation.xml.rels": relationships(
            [
                ("rId1", "slide", "slides/slide1.xml"),
                ("rId2", "slideMaster", "slideMasters/slideMaster1.xml"),
                ("rId3", "theme", "theme/theme1.xml"),
                ("rId4", "presProps", "presProps.xml"),
            ]
        ),
        "ppt/presProps.xml": f'<p:presentationPr xmlns:p="{presentation}"/>',
        "ppt/slides/_rels/slide1.xml.rels": relationships(
            [("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml")]
        ),
        "ppt/slideLayouts/slideLayout1.xml": f'<p:sldLayout {namespaces} type="blank" preserve="1"><p:cSld name="Trang trắng"><p:spTree>{group}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>',
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": relationships(
            [("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")]
        ),
        "ppt/slideMasters/slideMaster1.xml": f'<p:sldMaster {namespaces}><p:cSld><p:spTree>{group}</p:spTree></p:cSld><p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>',
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": relationships(
            [
                ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"),
                ("rId2", "theme", "../theme/theme1.xml"),
            ]
        ),
    }
    colors = [
        ("dk1", "1A1A19"),
        ("lt1", "FFFFFF"),
        ("dk2", "454541"),
        ("lt2", "F8F8F6"),
        ("accent1", "454541"),
        ("accent2", "6B6B66"),
        ("accent3", "8C8C85"),
        ("accent4", "ACACA5"),
        ("accent5", "CECEC7"),
        ("accent6", "E3E3DF"),
        ("hlink", "244A7B"),
        ("folHlink", "65517A"),
    ]
    scheme = (
        '<a:clrScheme name="BDSG">'
        + "".join(
            f'<a:{name}><a:srgbClr val="{color}"/></a:{name}>' for name, color in colors
        )
        + "</a:clrScheme>"
    )
    fonts = '<a:fontScheme name="BDSG"><a:majorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont><a:minorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
    fill = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    line = (
        '<a:ln w="12700">'
        + fill
        + '<a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>'
    )
    formatting = (
        '<a:fmtScheme name="BDSG"><a:fillStyleLst>'
        + fill * 3
        + "</a:fillStyleLst><a:lnStyleLst>"
        + line * 3
        + "</a:lnStyleLst><a:effectStyleLst>"
        + "<a:effectStyle><a:effectLst/></a:effectStyle>" * 3
        + "</a:effectStyleLst><a:bgFillStyleLst>"
        + fill * 3
        + "</a:bgFillStyleLst></a:fmtScheme>"
    )
    files["ppt/theme/theme1.xml"] = (
        f'<a:theme xmlns:a="{drawing}" name="BDSG"><a:themeElements>{scheme}{fonts}{formatting}</a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>'
    )
    return files, [
        ("ppt/slideLayouts/slideLayout1.xml", "presentationml.slideLayout+xml"),
        ("ppt/slideMasters/slideMaster1.xml", "presentationml.slideMaster+xml"),
        ("ppt/theme/theme1.xml", "theme+xml"),
        ("ppt/presProps.xml", "presentationml.presProps+xml"),
    ]
