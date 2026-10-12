from pathlib import Path
from zipfile import ZipFile

import pytest

from app.services.extraction import ExtractionError, extract

CORPUS = Path(__file__).resolve().parents[2] / "evaluation/corpus"


def test_three_formats_and_physical_locations(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_bytes("\ufeffPremier point.\n\nTroisième ligne.\n".encode())
    units = extract(source, "txt")
    assert [(u.number, u.text, u.kind) for u in units] == [
        (1, "Premier point.", "line"),
        (3, "Troisième ligne.", "line"),
    ]
    pdf = extract(CORPUS / "atelier-rag.pdf", "pdf")
    assert [u.number for u in pdf] == [1, 2, 3]
    assert all(u.kind == "page" and u.text for u in pdf)
    docx = extract(CORPUS / "parcours-2026.docx", "docx")
    assert docx and all(u.kind == "paragraph" for u in docx)
    assert [u.number for u in docx] == sorted(u.number for u in docx)


@pytest.mark.parametrize(
    "name,extension,code",
    [
        ("scan.pdf", "pdf", "no_text"),
        ("corrompu.pdf", "pdf", "invalid_file"),
        ("vide.txt", "txt", "no_text"),
        ("reseau.txt", "pdf", "invalid_file"),
    ],
)
def test_invalid_corpus(name: str, extension: str, code: str) -> None:
    with pytest.raises(ExtractionError) as caught:
        extract(CORPUS / name, extension)
    assert caught.value.code == code


def test_utf8_and_extraction_limits(tmp_path: Path) -> None:
    source = tmp_path / "bad.txt"
    for content, code in [
        (b"\xff", "invalid_encoding"),
        (b"a\x00b", "invalid_file"),
        (b"a" * 2_000_001, "extraction_limit"),
    ]:
        source.write_bytes(content)
        with pytest.raises(ExtractionError) as caught:
            extract(source, "txt")
        assert caught.value.code == code


def test_docx_decompression_entities_and_table_order(tmp_path: Path) -> None:
    path = tmp_path / "doc.docx"

    def write(xml: bytes) -> None:
        with ZipFile(path, "w") as archive:
            archive.writestr("[Content_Types].xml", b"<Types/>")
            archive.writestr("word/document.xml", xml)

    write(
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordproces'
        b'singml/2006/main"><w:body><w:p><w:r><w:t>Avant</w:t></w:r></w:p><'
        b"w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cellule</w:t></w:r></w:p></w:tc>"
        b"</w:tr></w:tbl><w:p><w:r><w:t>Apres</w:t></w:r></w:p></w:body></w"
        b":document>"
    )
    assert [u.text for u in extract(path, "docx")] == ["Avant", "Cellule", "Apres"]
    write(b'<!DOCTYPE x [<!ENTITY test "expanded">]><x>&test;</x>')
    with pytest.raises(ExtractionError):
        extract(path, "docx")
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", b"a" * 1_000_001)
        archive.writestr("[Content_Types].xml", b"<Types/>")
    with pytest.raises(ExtractionError):
        extract(path, "docx", max_uncompressed=1_000_000)


def test_twenty_mebibyte_text_is_supported(tmp_path: Path) -> None:
    source = tmp_path / "limit.txt"
    source.write_bytes(
        b"Document de vingt Mio.\n" + b" " * (20 * 1024 * 1024 - len(b"Document de vingt Mio.\n"))
    )
    assert source.stat().st_size == 20 * 1024 * 1024
    assert extract(source, "txt")[0].text == "Document de vingt Mio."


def test_encrypted_pdf_and_blank_physical_page(tmp_path: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    path = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("password")
    writer.write(path)
    with pytest.raises(ExtractionError) as caught:
        extract(path, "pdf")
    assert caught.value.code == "encrypted_file"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    for page in PdfReader(CORPUS / "atelier-rag.pdf").pages:
        writer.add_page(page)
    writer.write(path)
    assert [unit.number for unit in extract(path, "pdf")] == [2, 3, 4]
