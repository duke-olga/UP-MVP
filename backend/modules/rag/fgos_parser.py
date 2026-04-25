"""Parse FGOS VO PDF documents into text chunks for RAG retrieval.

FGOS PDFs live under backend/seed/fgosvo/{09.03.XX}/*.pdf.
Text is extracted page-by-page with PyMuPDF, page headers cleaned,
then split on numbered sections (1.1., 2.4., I., II., etc.).
"""
from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF

from backend.modules.rag.chunker import Chunk

FGOS_DIR = Path(__file__).resolve().parents[2] / "seed" / "fgosvo"

# Maps compact program_code (090304) to subfolder name (09.03.04)
_FOLDER_MAP: dict[str, str] = {
    "090301": "09.03.01",
    "090302": "09.03.02",
    "090303": "09.03.03",
    "090304": "09.03.04",
}

# Per-program cache so PDFs are parsed only once per server lifetime.
_fgos_chunk_cache: dict[str, list[Chunk]] = {}

# Page-header lines that repeat on every page — remove them from the corpus.
_HEADER_RE = re.compile(
    r"^(?:"
    r"Приказ Министерства образования.*"
    r"|Редакция с изменениями.*"
    r"|Система ГАРАНТ\s*"            # sometimes has trailing space
    r"|\d{1,2}\.\d{2}\.\d{4}\s*"   # dates like 15.06.2021
    r"|\d+/\d+\s*"                   # page numbers like 4/12
    r"|=== Page \d+ ==="
    r")$",
    re.MULTILINE,
)
_BLANK_LINES_RE = re.compile(r"\n{3,}")
# A paragraph break (double newline) that is actually a soft wrap: previous "paragraph" ends
# without sentence-stopping punctuation and its last word looks like a continuation.
_SOFT_PARA_BREAK_RE = re.compile(r"([^.!?;:\n])\n\n([а-яёa-z(«])", re.MULTILINE)

# Section-number pattern: "2.4.", "1.11.", "4.6.3." or Roman numeral "II."
# First digit [1-9] (not two-digit) to exclude dates like 15.06.2021.
_SECTION_RE = re.compile(
    r"(?m)^([1-9]\d?\.\d+(?:\.\d+)?\.?\s|(?:I{1,3}|IV|VI{0,3}|IX|X{1,3})\.\s)",
)

_MIN_CHUNK_LEN = 80   # chars — skip sections shorter than this
_MAX_CHUNK_LEN = 1400  # chars — cap to keep embeddings focused

# Lines that end WITHOUT sentence-stopping punctuation are PDF layout wraps — join them.
# Exclude trailing hyphen/dash that is a continuation marker (e.g. "вместе -"), not sentence end.
_SENTENCE_END = re.compile(r"[.!?;:]$")
# List-item prefix: "- word" or "• word"
_LIST_ITEM = re.compile(r"^\s*[-•]\s")


def _extract_full_text(pdf_path: Path) -> str:
    doc = fitz.open(str(pdf_path))
    return "\n".join(page.get_text() for page in doc)


def _join_wrapped_lines(text: str) -> str:
    """Join lines that were soft-wrapped by the PDF renderer.

    A line is a continuation if:
    - the previous line does NOT end with sentence-stopping punctuation, AND
    - the current line does NOT start a new list item or a section number.
    """
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not result:
            result.append(stripped)
            continue
        prev = result[-1]
        # Keep as separate line if: blank, starts a list item, starts a section number, or prev ends a sentence
        if (
            not stripped
            or not prev
            or _LIST_ITEM.match(stripped)
            or _SECTION_RE.match(stripped)
            or _SENTENCE_END.search(prev)
        ):
            result.append(stripped)
        else:
            result[-1] = prev + " " + stripped
    return "\n".join(result)


def _clean(text: str) -> str:
    text = _HEADER_RE.sub("", text)
    text = _join_wrapped_lines(text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    # Collapse soft paragraph breaks: double-newline inside a sentence continuation
    text = _SOFT_PARA_BREAK_RE.sub(r"\1 \2", text)
    return text.strip()


def _clean_chunk(text: str) -> str:
    """Remove residual page-header lines and re-join any wrapped lines."""
    text = _HEADER_RE.sub("", text)
    text = _join_wrapped_lines(text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    text = _SOFT_PARA_BREAK_RE.sub(r"\1 \2", text)
    return text.strip()


def _split_into_chunks(text: str, program_code: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    positions = [(m.start(), m.group(0).strip()) for m in _SECTION_RE.finditer(text)]

    for i, (start, section_id) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        raw = _clean_chunk(text[start:end])
        if len(raw) < _MIN_CHUNK_LEN:
            continue
        label = f"ФГОС ВО {program_code}, п. {section_id}"
        chunks.append(Chunk(text=raw[:_MAX_CHUNK_LEN], source_type="fgos", source_label=label))

    # Fallback for documents without numbered sections
    if not chunks:
        for para in text.split("\n\n"):
            para = _clean_chunk(para)
            if len(para) >= _MIN_CHUNK_LEN:
                chunks.append(Chunk(
                    text=para[:_MAX_CHUNK_LEN],
                    source_type="fgos",
                    source_label=f"ФГОС ВО {program_code}",
                ))

    return chunks


def load_fgos_chunks(program_code: str) -> list[Chunk]:
    """Return cached FGOS chunks for *program_code*; empty list if no PDF found."""
    if program_code in _fgos_chunk_cache:
        return _fgos_chunk_cache[program_code]

    folder_name = _FOLDER_MAP.get(program_code)
    if not folder_name:
        _fgos_chunk_cache[program_code] = []
        return []

    fgos_dir = FGOS_DIR / folder_name
    pdf_files = sorted(fgos_dir.glob("*.pdf")) if fgos_dir.exists() else []
    if not pdf_files:
        _fgos_chunk_cache[program_code] = []
        return []

    try:
        raw = _extract_full_text(pdf_files[0])
        chunks = _split_into_chunks(_clean(raw), program_code)
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).error(
            "FGOS PDF parse failed for program %s (%s): %s",
            program_code, pdf_files[0], exc, exc_info=True,
        )
        chunks = []

    _fgos_chunk_cache[program_code] = chunks
    return chunks
