"""Canonical extraction only. No embeddings and no network requests."""

import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree  # type: ignore[import-untyped]
from pypdf import PdfReader

PARSER_VERSION = "canonical-v1:pypdf-6.19.0:docx-xml:txt-utf8"
MAX_CHARACTERS = 2_000_000
MAX_UNITS = 10_000


class ExtractionError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ExtractedUnit:
    kind: str
    number: int
    text: str


def canonical_text(value: str) -> str:
    value = value.strip()
    return "".join(c for c in value if c in "\n\t" or unicodedata.category(c) != "Cc").strip()


def extract(
    path: Path, extension: str, max_uncompressed: int = 50 * 1024 * 1024
) -> list[ExtractedUnit]:
    units: list[ExtractedUnit] = []
    characters = 0

    def add(kind: str, number: int, value: str) -> None:
        nonlocal characters
        value = canonical_text(value)
        characters += len(value)
        if characters > MAX_CHARACTERS or number > MAX_UNITS or len(value.encode("utf-8")) > 65536:
            raise ExtractionError("extraction_limit")
        if value:
            units.append(ExtractedUnit(kind, number, value))

    try:
        if extension == "txt":
            raw = path.read_bytes()
            if b"\x00" in raw or raw.startswith((b"%PDF", b"PK\x03\x04")):
                raise ExtractionError("invalid_file")
            for number, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
                add("line", number, line)
        elif extension == "pdf":
            with path.open("rb") as stream:
                if stream.read(5) != b"%PDF-":
                    raise ExtractionError("invalid_file")
                stream.seek(0)
                # Suppress parser diagnostics: malformed files may contain private data.
                logging.getLogger("pypdf").disabled = True
                reader = PdfReader(stream, strict=True)
                if reader.is_encrypted:
                    raise ExtractionError("encrypted_file")
                if len(reader.pages) > 500:
                    raise ExtractionError("extraction_limit")
                for number, page in enumerate(reader.pages, 1):
                    add("page", number, page.extract_text())
        elif extension == "docx":
            with ZipFile(path) as archive:
                members = archive.infolist()
                names = [m.filename for m in members]
                if len(names) != len(set(names)) or len(members) > 2000:
                    raise ExtractionError("invalid_file")
                if sum(m.file_size for m in members) > max_uncompressed:
                    raise ExtractionError("extraction_limit")
                if any(m.flag_bits & 1 for m in members):
                    raise ExtractionError("encrypted_file")
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise ExtractionError("invalid_file")
                # No ZIP paths are extracted to disk and XML never resolves entities.
                root = ElementTree.fromstring(archive.read("word/document.xml"), forbid_dtd=True)
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                if root.tag != ns + "document":
                    raise ExtractionError("invalid_file")
                body = root.find(ns + "body")
                if body is None:
                    raise ExtractionError("invalid_file")
                for number, paragraph in enumerate(body.iter(ns + "p"), 1):
                    parts = []
                    for node in paragraph.iter():
                        if node.tag == ns + "t":
                            parts.append(node.text or "")
                        elif node.tag == ns + "tab":
                            parts.append("\t")
                        elif node.tag in {ns + "br", ns + "cr"}:
                            parts.append("\n")
                    add("paragraph", number, "".join(parts))
        else:
            raise ExtractionError("invalid_file")
    except ExtractionError:
        raise
    except UnicodeDecodeError as error:
        raise ExtractionError("invalid_encoding") from error
    except (Exception, BadZipFile) as error:
        raise ExtractionError("invalid_file") from error
    if not units:
        raise ExtractionError("no_text")
    return units
