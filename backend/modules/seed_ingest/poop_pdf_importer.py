from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import fitz
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
DEFAULT_POOP_DIR = SEED_DIR / "poop_pdf"
DEFAULT_BEST_PRACTICES_DIR = SEED_DIR / "best_practices_pdf"
DEFAULT_OUTPUT_PATH = SEED_DIR / "poop_disciplines.json"
DEFAULT_REPORT_PATH = SEED_DIR / "poop_import_report.json"
DEFAULT_MANIFEST_PATH = SEED_DIR / "poop_import_manifest.json"
DEFAULT_REVIEW_DIR = SEED_DIR / "poop_review_dump"
IMPORT_STRATEGIES = ("deterministic",)

COMPETENCY_CODE_RE = re.compile(r"(?:УК|ОПК|ПКС|ПК)-\d+")
ROW_ID_CODE_RE = re.compile(r"^(?:Б\d[\w./-]*|B\d[\w./-]*|ФТД[\w./-]*|ГИА[\w./-]*)$", re.IGNORECASE)

START_HINTS = ("примерный учебный план", "учебный план")
STOP_HINTS = ("учебный план согласован", "код компетенции", "календарный учебный график")
TABLE_HEADER_HINTS = ("наименование", "трудоемк", "з.е", "компетенц", "индекс", "вид дисциплины")
NON_PLAN_TABLE_HINTS = (
    "код и наименование индикатора",
    "оценочных средств",
    "текущего контроля",
    "наименование темы",
    "вид учебных занятий",
    "задачи профессиональной деятельности",
    "краткая характеристика",
)
SUMMARY_HINTS = (
    "вся образовательная программа",
    "major",
    "всего",
    "итого",
    "обязательная часть",
    "вариативная часть",
    "часть блока",
    "базовая часть",
    "базовые дисциплины",
    "обязательные дисциплины",
    "дополнительные дисциплины",
    "фиксированный",
    "формируются образовательной организацией самостоятельно",
    "устанавливается образовательной организацией",
)
SUMMARY_PREFIX_HINTS = (
    "блок",
    "major",
    "профессиональная подготовка",
    "профессиональный модуль",
    "модуль специализации",
    "специализация",
    "базовые дисциплины",
    "обязательные дисциплины",
    "базовый профессиональный",
    "вариативный профессиональный",
    "подготовка вкр",
    "гия",
    "научно-исследовательский семинар",
    "software engineering",
    "software engeneering",
    "компьютерные науки",
)
IGNORE_NAME_HINTS = (
    "выпускной квалификационной работы",
    "защита выпускной",
    "курсовой проект",
)
MANDATORY_HINTS = ("обязательная часть", "базовая часть", "обязательные дисциплины", "фиксированный")
VARIATIVE_HINTS = ("вариативная часть", "по выбору", "дополнительные дисциплины", "факультатив")
FGOS_DISCIPLINE_RULES: dict[str, tuple[str, ...]] = {
    "philosophy": ("философ",),
    "history": ("история",),
    "foreign_language": ("иностранн",),
    "life_safety": ("безопасност", "жизнедеятель"),
}


class PoopDisciplineSeedRecord(BaseModel):
    direction_code: str = Field(pattern=r"^\d{6}$")
    source_name: str
    source_type: Literal["poop", "best_practices"]
    name: str
    element_type: Literal["discipline", "practice"]
    part: Literal["mandatory", "variative"]
    credits: float
    semesters: list[int]
    competency_codes: list[str]
    practice_type: Literal["educational", "industrial"] | None = None
    fgos_mandatory: Literal[
        "philosophy",
        "history",
        "foreign_language",
        "life_safety",
    ] | None = None


class ImportReportEntry(BaseModel):
    direction_code: str
    source_name: str
    source_type: Literal["poop", "best_practices"]
    strategy_used: Literal["deterministic"]
    extractor_used: Literal["pymupdf", "docling", "pypdf", "text", "none"]
    candidate_row_count: int
    record_count: int
    quality_score: float
    needs_review: bool
    warnings: list[str]
    candidate_samples: list[dict]


class ImportManifestEntry(BaseModel):
    source_name: str
    source_type: Literal["poop", "best_practices"]
    file_size_bytes: int
    sha256: str
    strategy_used: Literal["deterministic"]
    extractor_used: Literal["pymupdf", "docling", "pypdf", "text", "none"]
    record_count: int
    quality_score: float
    needs_review: bool


@dataclass(frozen=True)
class SeedSourceConfig:
    source_type: Literal["poop", "best_practices"]
    input_dir: Path


@dataclass
class TableBlock:
    page_number: int
    rows: list[list[str]]
    page_text: str
    extractor: Literal["pymupdf", "docling", "pypdf"]


@dataclass
class ParserState:
    part: Literal["mandatory", "variative"] = "mandatory"
    current_group: str = ""
    semester_columns: dict[int, int] = field(default_factory=dict)
    first_column_is_semester: bool = False


@dataclass
class CandidateRow:
    page_number: int
    extractor: Literal["pymupdf", "docling", "pypdf", "text"]
    source_name: str
    source_type: Literal["poop", "best_practices"]
    row_id: str
    name: str
    cells: list[str]
    row_text: str
    credits_candidate: float | None
    semesters_candidate: list[int]
    competency_codes_candidate: list[str]
    part_candidate: Literal["mandatory", "variative"]
    kind_cell: str | None


@dataclass
class FileAnalysis:
    records: list[PoopDisciplineSeedRecord]
    candidate_rows: list[CandidateRow]
    extractor_used: Literal["pymupdf", "docling", "pypdf", "text", "none"]
    quality_score: float
    needs_review: bool
    warnings: list[str]
    strategy_used: Literal["deterministic"]


SOURCE_CONFIGS: tuple[SeedSourceConfig, ...] = (
    SeedSourceConfig(
        source_type="poop",
        input_dir=DEFAULT_POOP_DIR,
    ),
    SeedSourceConfig(
        source_type="best_practices",
        input_dir=DEFAULT_BEST_PRACTICES_DIR,
    ),
)
SOURCE_CONFIG_MAP = {config.source_type: config for config in SOURCE_CONFIGS}


LLM_SYSTEM_PROMPT = """
Ты извлекаешь из текста PDF только элементы учебного плана и возвращаешь только JSON-массив.
Без Markdown, без пояснений, без дополнительных полей.

Никогда не додумывай значения полей.
Если в документе нет явных кодов компетенций, верни "competency_codes": [].
Если семестры не указаны явно, верни "semesters": [].
Заполняй поля только по прямым данным из документа.

Игнорируй:
- агрегаты по блокам;
- итоги и диапазоны кредитов;
- подписи, согласования, реквизиты;
- описания компетенций;
- календарный учебный график;
- строки без конкретного названия дисциплины или практики.

Схема объекта:
{
  "name": "string",
  "element_type": "discipline | practice",
  "part": "mandatory | variative",
  "credits": number,
  "semesters": [int],
  "competency_codes": ["УК-1", "ОПК-2"],
  "practice_type": "educational | industrial | null",
  "fgos_mandatory": "philosophy | history | foreign_language | life_safety | null"
}
""".strip()


def _get_source_config(source_type: Literal["poop", "best_practices"]) -> SeedSourceConfig:
    return SOURCE_CONFIG_MAP[source_type]


def _normalize_cell(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _normalize_name(raw_value: str) -> str:
    return _normalize_cell(raw_value).strip(" .;:")


def _extract_competency_codes(raw_value: str) -> list[str]:
    seen: set[str] = set()
    codes: list[str] = []
    for code in COMPETENCY_CODE_RE.findall(raw_value):
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def _extract_json_array(raw_text: str) -> list[dict]:
    start = raw_text.find("[")
    end = raw_text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("LLM response does not contain a JSON array")
    payload = raw_text[start : end + 1]
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError("LLM response JSON root must be a list")
    return data


def _parse_float(raw_value: str) -> float | None:
    match = re.search(r"\d+(?:[.,]\d+)?", raw_value)
    if match is None:
        return None
    return float(match.group(0).replace(",", "."))


def _is_kind_cell(value: str) -> bool:
    lowered = value.casefold()
    return lowered in {"о", "в", "ф", "обязательный предмет", "предмет по выбору", "факультатив"}


def _detect_part(row_text: str, kind_cell: str | None, current_part: Literal["mandatory", "variative"]) -> Literal["mandatory", "variative"]:
    lowered = row_text.casefold()
    if kind_cell:
        kind_lower = kind_cell.casefold()
        if kind_lower == "о":
            return "mandatory"
        if kind_lower in {"в", "ф"}:
            return "variative"
    if any(marker in lowered for marker in MANDATORY_HINTS):
        return "mandatory"
    if any(marker in lowered for marker in VARIATIVE_HINTS):
        return "variative"
    return current_part


def _detect_fgos_mandatory(name: str) -> str | None:
    haystack = name.casefold()
    for mandatory_code, markers in FGOS_DISCIPLINE_RULES.items():
        if all(marker in haystack for marker in markers):
            return mandatory_code
    return None


def _detect_practice_type(name: str, row_id: str = "") -> str | None:
    normalized_row_id = row_id.replace(" ", "").upper()
    if ".У" in normalized_row_id or normalized_row_id.startswith("У"):
        return "educational"
    if ".П" in normalized_row_id or normalized_row_id.startswith("П"):
        return "industrial"

    lowered = name.casefold()
    if "учебн" in lowered:
        return "educational"
    if any(marker in lowered for marker in ("практик", "преддиплом", "технологическ", "эксплуатационн", "производственн")):
        return "industrial"
    return None


def _looks_like_row_identifier(value: str) -> bool:
    cleaned = _normalize_cell(value).replace(" ", "")
    if not cleaned:
        return False
    if re.fullmatch(r"\d{1,3}", cleaned):
        return True
    if re.fullmatch(r"[IVXLCDM]+", cleaned, re.IGNORECASE):
        return False
    if ROW_ID_CODE_RE.fullmatch(cleaned):
        return True
    return cleaned.startswith(("Б1", "Б2", "Б3", "B1", "B2", "B3", "ФТД", "ГИА"))


def _looks_like_candidate_name(name: str) -> bool:
    normalized = _normalize_name(name)
    if not normalized:
        return False
    if len(normalized) > 180:
        return False
    if len(normalized.split()) > 18:
        return False
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", normalized)
    if len(letters) < 3:
        return False
    if re.fullmatch(r"[\d\W_]+", normalized):
        return False
    lowered = normalized.casefold()
    banned_fragments = (
        "учебный план",
        "пояснительная записка",
        "годы обучения",
        "срок обучения",
        "форма обучения",
        "месяцы",
        "недели",
        "вопросы к экзамену",
        "код компетенции",
    )
    return not any(fragment in lowered for fragment in banned_fragments)


def _is_summary_name(name: str) -> bool:
    lowered = name.casefold()
    if any(marker in lowered for marker in SUMMARY_HINTS):
        return True
    return any(lowered.startswith(marker) for marker in SUMMARY_PREFIX_HINTS)


def _is_aggregate_plan_name(name: str) -> bool:
    lowered = _normalize_name(name).casefold()
    aggregate_markers = (
        "\u0434\u0438\u0441\u0446\u0438\u043f\u043b\u0438\u043d\u044b \u043f\u043e \u0432\u044b\u0431\u043e\u0440\u0443",
        "\u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0438 \u043f\u043e \u0432\u044b\u0431\u043e\u0440\u0443",
        "\u044d\u043b\u0435\u043a\u0442\u0438\u0432\u043d\u044b\u0435 \u0434\u0438\u0441\u0446\u0438\u043f\u043b\u0438\u043d\u044b",
        "\u0444\u0430\u043a\u0443\u043b\u044c\u0442\u0430\u0442\u0438\u0432\u043d\u044b\u0435 \u0434\u0438\u0441\u0446\u0438\u043f\u043b\u0438\u043d\u044b",
        "\u043c\u043e\u0434\u0443\u043b\u0438 \u043f\u043e \u0432\u044b\u0431\u043e\u0440\u0443",
    )
    return any(marker in lowered for marker in aggregate_markers)


def _find_credit_candidates(cells: list[str]) -> list[float]:
    values: list[float] = []
    for cell in cells:
        value = _parse_float(cell)
        if value is None:
            continue
        if 0 < value <= 60:
            values.append(value)
    return values


def _extract_name_and_tail(row: list[str]) -> tuple[str, list[str], str | None]:
    nonempty = [cell for cell in row if cell]
    if len(nonempty) < 2:
        return "", [], None
    start = 1 if _looks_like_row_identifier(nonempty[0]) else 0
    if len(nonempty) <= start:
        return "", [], None
    name = _normalize_name(nonempty[start])
    remainder = nonempty[start + 1 :]
    kind_cell = next((cell for cell in remainder if _is_kind_cell(cell)), None)
    return name, remainder, kind_cell


def _row_looks_like_plan_candidate(row: list[str]) -> bool:
    nonempty = [cell for cell in row if cell]
    if len(nonempty) < 2:
        return False
    if not _looks_like_row_identifier(nonempty[0]):
        return False
    if not _looks_like_candidate_name(nonempty[1]):
        return False
    if _is_summary_name(nonempty[1]):
        return False
    return bool(_find_credit_candidates(nonempty[2:] or nonempty))


def _table_looks_like_plan(page_text: str, rows: list[list[str]]) -> bool:
    if not rows:
        return False
    header_text = " ".join(" ".join(cell for cell in row if cell) for row in rows[:8]).casefold()
    page_lower = page_text.casefold()
    if any(marker in header_text or marker in page_lower for marker in NON_PLAN_TABLE_HINTS):
        return False

    score = 0
    if any(marker in page_lower for marker in START_HINTS):
        score += 3
    if "учебный план" in header_text:
        score += 2
    if "наименование" in header_text:
        score += 1
    if "трудоемк" in header_text or "з.е" in header_text or "зачетных единиц" in header_text:
        score += 2
    if "компетенц" in header_text:
        score += 2
    if "семестр" in header_text or "распределение" in header_text or "семестры старта" in header_text:
        score += 1

    candidate_rows = sum(1 for row in rows[:20] if _row_looks_like_plan_candidate(row))
    if candidate_rows >= 2:
        score += 2
    if candidate_rows >= 5:
        score += 1
    return score >= 4 and candidate_rows >= 1


def _table_looks_like_continuation(page_text: str, rows: list[list[str]]) -> bool:
    if not rows:
        return False
    header_text = " ".join(" ".join(cell for cell in row if cell) for row in rows[:6]).casefold()
    page_lower = page_text.casefold()
    if any(marker in header_text or marker in page_lower for marker in NON_PLAN_TABLE_HINTS):
        return False
    return sum(1 for row in rows[:20] if _row_looks_like_plan_candidate(row)) >= 1


def _extract_table_blocks_with_pymupdf(pdf_path: Path) -> list[TableBlock]:
    blocks: list[TableBlock] = []
    in_plan_section = False
    with fitz.open(pdf_path) as document:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            page_text = page.get_text("text")
            tables = page.find_tables()
            page_blocks: list[TableBlock] = []
            for table in tables.tables:
                rows = [[_normalize_cell(cell) for cell in row] for row in table.extract()]
                if _table_looks_like_plan(page_text, rows):
                    page_blocks.append(TableBlock(page_number=page_index + 1, rows=rows, page_text=page_text, extractor="pymupdf"))
                    continue
                if in_plan_section and _table_looks_like_continuation(page_text, rows):
                    page_blocks.append(TableBlock(page_number=page_index + 1, rows=rows, page_text=page_text, extractor="pymupdf"))
            if page_blocks:
                blocks.extend(page_blocks)
                in_plan_section = True
                continue
            if in_plan_section and any(marker in page_text.casefold() for marker in STOP_HINTS):
                break
    return blocks


def _parse_markdown_table(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.count("|") < 2:
            continue
        if set(stripped.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")) == set():
            continue
        cells = [_normalize_cell(cell) for cell in stripped.strip("|").split("|")]
        rows.append(cells)
    return rows


def _extract_table_blocks_with_docling(pdf_path: Path) -> tuple[list[TableBlock], list[str]]:
    warnings: list[str] = []
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except Exception as exc:
        warnings.append(f"docling_unavailable: {exc}")
        return [], warnings

    try:
        pipeline_options = PdfPipelineOptions(do_ocr=False, force_backend_text=True)
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
        result = converter.convert(str(pdf_path))
    except Exception as exc:
        warnings.append(f"docling_convert_failed: {exc}")
        return [], warnings

    markdown = ""
    document = getattr(result, "document", None)
    if document is not None:
        export_to_markdown = getattr(document, "export_to_markdown", None)
        if callable(export_to_markdown):
            markdown = export_to_markdown()
    if not markdown:
        export_to_markdown = getattr(result, "export_to_markdown", None)
        if callable(export_to_markdown):
            markdown = export_to_markdown()
    if not markdown:
        warnings.append("docling_no_markdown")
        return [], warnings

    table_rows = _parse_markdown_table(markdown)
    if not table_rows:
        warnings.append("docling_no_tables")
        return [], warnings

    block = TableBlock(page_number=1, rows=table_rows, page_text=markdown, extractor="docling")
    if _table_looks_like_plan(markdown, table_rows) or _table_looks_like_continuation(markdown, table_rows):
        return [block], warnings
    warnings.append("docling_tables_not_plan_like")
    return [], warnings


def _extract_table_blocks_with_pypdf(pdf_path: Path) -> tuple[list[TableBlock], list[str]]:
    warnings: list[str] = []
    try:
        from pypdf import PdfReader
    except Exception as exc:
        warnings.append(f"pypdf_unavailable: {exc}")
        return [], warnings

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        warnings.append(f"pypdf_open_failed: {exc}")
        return [], warnings

    blocks: list[TableBlock] = []
    in_plan_section = False
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            page_text = _normalize_cell(page.extract_text() or "")
        except Exception as exc:
            warnings.append(f"pypdf_extract_failed: page={page_number} error={exc}")
            continue
        lowered = page_text.casefold()
        if not in_plan_section and any(marker in lowered for marker in START_HINTS):
            in_plan_section = True
        if not in_plan_section:
            continue
        if any(marker in lowered for marker in STOP_HINTS):
            break

        lines = [line.strip() for line in page_text.split("  ") if line.strip()]
        pseudo_rows = [[_normalize_cell(line)] for line in lines if line]
        if pseudo_rows:
            blocks.append(TableBlock(page_number=page_number, rows=pseudo_rows, page_text=page_text, extractor="pypdf"))

    if not blocks:
        warnings.append("pypdf_no_plan_text")
    return blocks, warnings


def _extract_plan_section_texts(pdf_path: Path) -> list[tuple[int, str]]:
    sections: list[tuple[int, str]] = []
    in_plan_section = False
    with fitz.open(pdf_path) as document:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            text = page.get_text("text")
            lowered = text.casefold()
            if not in_plan_section and ("5.3" in lowered and any(marker in lowered for marker in START_HINTS)):
                in_plan_section = True
            if not in_plan_section:
                continue
            if any(marker in lowered for marker in STOP_HINTS):
                break
            sections.append((page_index + 1, text))
    return sections


def _pdf_contains_plan_markers(pdf_path: Path) -> bool:
    with fitz.open(pdf_path) as document:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            text = _normalize_cell(page.get_text("text"))
            if not text:
                continue
            lowered = text.casefold()
            if any(marker in lowered for marker in START_HINTS):
                return True
            if "5.3" in lowered and ("компетенц" in lowered or "трудоемк" in lowered or "з.е" in lowered):
                return True
            if any(marker in lowered for marker in TABLE_HEADER_HINTS):
                return True
    return False


def _normalize_text_lines(text: str) -> list[str]:
    raw_lines = [line.strip() for line in text.splitlines()]
    return [_normalize_cell(line) for line in raw_lines if _normalize_cell(line)]


def _looks_like_competency_only_line(line: str) -> bool:
    tokens = _extract_competency_codes(line)
    return bool(tokens) and re.sub(r"(УК|ОПК|ПКС|ПК)-\d+|[.,;:\s]", "", line) == ""


def _looks_like_partial_row_id(line: str) -> bool:
    return _looks_like_row_identifier(line) and len(line.split()) == 1


def _looks_like_text_row_identifier(value: str) -> bool:
    normalized = _normalize_cell(value).replace(" ", "")
    return _looks_like_row_identifier(normalized) and not normalized.isdigit()


def _line_starts_candidate(line: str) -> bool:
    if not line:
        return False
    row_id, remainder = _extract_row_id_and_remainder(line)
    if not row_id or not _looks_like_text_row_identifier(row_id):
        return False
    if not remainder:
        return True
    if _looks_like_structural_text_line(remainder):
        return False
    if len(remainder) <= 2 and remainder.isdigit():
        return True
    return _looks_like_candidate_name(remainder) or bool(_extract_competency_codes(remainder))


def _merge_broken_plan_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    index = 0
    while index < len(lines):
        current = lines[index]
        if _looks_like_partial_row_id(current) and index + 1 < len(lines):
            current = f"{current} {lines[index + 1]}"
            index += 1
        if merged and _looks_like_competency_only_line(current):
            merged[-1] = f"{merged[-1]} {current}"
        else:
            merged.append(current)
        index += 1
    return merged


def _extract_row_id_and_remainder(line: str) -> tuple[str | None, str]:
    tokens = line.split()
    if not tokens:
        return None, ""
    if len(tokens) >= 2 and tokens[0].isdigit() and _looks_like_text_row_identifier(tokens[1]):
        return _normalize_cell(tokens[1]), _normalize_cell(" ".join(tokens[2:]))
    if _looks_like_text_row_identifier(tokens[0]):
        if len(tokens) >= 2 and tokens[1].isdigit() and _looks_like_text_row_identifier(f"{tokens[0]}{tokens[1]}"):
            return _normalize_cell(f"{tokens[0]}{tokens[1]}"), _normalize_cell(" ".join(tokens[2:]))
        return _normalize_cell(tokens[0]), _normalize_cell(" ".join(tokens[1:]))
    if len(tokens) >= 2 and _looks_like_text_row_identifier(f"{tokens[0]}{tokens[1]}"):
        return _normalize_cell(f"{tokens[0]}{tokens[1]}"), _normalize_cell(" ".join(tokens[2:]))
    return None, line


def _looks_like_structural_text_line(line: str) -> bool:
    lowered = line.casefold()
    if any(marker in lowered for marker in START_HINTS):
        return True
    if any(marker in lowered for marker in STOP_HINTS):
        return True
    if any(marker in lowered for marker in SUMMARY_HINTS):
        return True
    return lowered in {"индекс наименование", "формы", "промежуточной", "трудоемкость,", "з.е.", "аттестации"}


def _candidate_from_text_line(
    row_lines: list[str],
    *,
    page_number: int,
    source_name: str,
    source_type: Literal["poop", "best_practices"],
    current_part: Literal["mandatory", "variative"],
) -> CandidateRow | None:
    if not row_lines:
        return None
    row_id, first_remainder = _extract_row_id_and_remainder(row_lines[0])
    if not row_id:
        return None
    row_text = _normalize_cell(" ".join(row_lines))
    remainder = _normalize_cell(" ".join(part for part in [first_remainder, *row_lines[1:]] if part))
    if not remainder:
        return None

    competency_codes = _extract_competency_codes(remainder)
    remainder_wo_comp = COMPETENCY_CODE_RE.sub(" ", remainder)
    remainder_wo_comp = re.sub(r"[✔✓✗×xX]+", " ", remainder_wo_comp)
    credit_matches = [
        match
        for match in re.finditer(r"\b\d+(?:[.,]\d+)?\b", remainder_wo_comp)
        if 0 < float(match.group(0).replace(",", ".")) <= 60
    ]
    if not credit_matches:
        return None
    credits_match = credit_matches[-1]
    credits_candidate = _parse_float(credits_match.group(0))
    if credits_candidate is None:
        return None
    prefix = _normalize_cell(remainder_wo_comp[: credits_match.start()])
    if not prefix:
        return None

    semesters_candidate = sorted({int(num) for num in re.findall(r"\b([1-9]|1[0-2])-\s*й\b", remainder) if 1 <= int(num) <= 12})

    name = re.sub(r"\s+[ОВФ]\s+", " ", prefix)
    kind_cell = None
    for marker in ("зачет", "экзамен", "курсов", "диф", "аттестаци", "консультац"):
        pos = name.casefold().find(marker)
        if pos > 0:
            name = name[:pos]
            break
    name = _normalize_name(name)
    if not _looks_like_candidate_name(name) or _is_summary_name(name) or _is_aggregate_plan_name(name):
        return None

    return CandidateRow(
        page_number=page_number,
        extractor="text",
        source_name=source_name,
        source_type=source_type,
        row_id=row_id,
        name=name,
        cells=row_lines,
        row_text=row_text,
        credits_candidate=credits_candidate,
        semesters_candidate=semesters_candidate,
        competency_codes_candidate=competency_codes,
        part_candidate=_detect_part(row_text, kind_cell, current_part),
        kind_cell=kind_cell,
    )


def _extract_candidate_rows_from_text_sections(
    pdf_path: Path,
    *,
    source_name: str,
    source_type: Literal["poop", "best_practices"],
) -> list[CandidateRow]:
    candidates: list[CandidateRow] = []
    current_part: Literal["mandatory", "variative"] = "mandatory"
    row_buffer: list[str] = []
    row_page_number: int | None = None

    def flush_buffer() -> None:
        nonlocal row_buffer, row_page_number
        if not row_buffer or row_page_number is None:
            row_buffer = []
            row_page_number = None
            return
        candidate = _candidate_from_text_line(
            row_buffer,
            page_number=row_page_number,
            source_name=source_name,
            source_type=source_type,
            current_part=current_part,
        )
        if candidate is not None:
            candidates.append(candidate)
        row_buffer = []
        row_page_number = None

    for page_number, text in _extract_plan_section_texts(pdf_path):
        lines = _merge_broken_plan_lines(_normalize_text_lines(text))
        for line in lines:
            current_part = _detect_part(line, None, current_part)
            lowered = line.casefold()
            if _looks_like_structural_text_line(line):
                flush_buffer()
                continue
            if _line_starts_candidate(line):
                flush_buffer()
                row_buffer = [line]
                row_page_number = page_number
                continue
            if not row_buffer:
                continue
            if any(marker in lowered for marker in SUMMARY_HINTS):
                flush_buffer()
                continue
            row_buffer.append(line)
        flush_buffer()
    return candidates


def _infer_semester_columns(rows: list[list[str]]) -> tuple[dict[int, int], bool]:
    semester_columns: dict[int, int] = {}
    first_column_is_semester = False
    for row in rows[:6]:
        joined = " ".join(cell for cell in row if cell)
        lowered = joined.casefold()
        if "семестры старта" in lowered:
            first_column_is_semester = True
        if "семестр" not in lowered and "триместр" not in lowered and "распределение" not in lowered and not re.search(r"\b1-\s*й\b", joined):
            continue
        for index, cell in enumerate(row):
            cleaned = _normalize_cell(cell).replace(" ", "")
            match = re.match(r"^(\d+)[-–]?(?:й)?$", cleaned)
            if match:
                semester = int(match.group(1))
                if 1 <= semester <= 12:
                    semester_columns[index] = semester
    if not semester_columns:
        max_width = max((len(row) for row in rows), default=0)
        if max_width >= 12:
            semester_columns = {index: semester for index, semester in zip(range(4, 12), range(1, 9))}
    return semester_columns, first_column_is_semester


def _extract_semesters_from_row(row: list[str], state: ParserState) -> list[int]:
    semesters: list[int] = []
    for index, semester in state.semester_columns.items():
        if index >= len(row):
            continue
        cell = _normalize_cell(row[index])
        lowered = cell.casefold()
        if "✔" in cell or "✓" in cell or "+" in cell or lowered in {"x", "х"}:
            semesters.append(semester)
    nonempty = [cell for cell in row if cell]
    if not semesters and state.first_column_is_semester and nonempty and nonempty[0].isdigit():
        semester = int(nonempty[0])
        if 1 <= semester <= 12:
            semesters.append(semester)
    return semesters


def _extract_candidate_rows_from_blocks(
    blocks: list[TableBlock],
    *,
    source_name: str,
    source_type: Literal["poop", "best_practices"],
) -> list[CandidateRow]:
    candidates: list[CandidateRow] = []
    for block in blocks:
        semester_columns, first_column_is_semester = _infer_semester_columns(block.rows)
        state = ParserState(semester_columns=semester_columns, first_column_is_semester=first_column_is_semester)
        for row in block.rows:
            row_text = " ".join(cell for cell in row if cell)
            if not row_text:
                continue
            lowered = row_text.casefold()
            state.part = _detect_part(row_text, None, state.part)
            if any(marker in lowered for marker in SUMMARY_HINTS):
                state.current_group = row_text
                continue

            nonempty = [cell for cell in row if cell]
            if len(nonempty) < 2 or not _looks_like_row_identifier(nonempty[0]):
                continue

            row_id = nonempty[0]
            name, tail_cells, kind_cell = _extract_name_and_tail(row)
            if not _looks_like_candidate_name(name) or _is_summary_name(name) or _is_aggregate_plan_name(name):
                continue
            if any(marker in name.casefold() for marker in IGNORE_NAME_HINTS):
                continue

            credits_candidates = _find_credit_candidates(tail_cells or row)
            if not credits_candidates:
                continue

            candidate = CandidateRow(
                page_number=block.page_number,
                extractor=block.extractor,
                source_name=source_name,
                source_type=source_type,
                row_id=row_id,
                name=name,
                cells=[cell for cell in row if cell],
                row_text=row_text,
                credits_candidate=credits_candidates[0],
                semesters_candidate=_extract_semesters_from_row(row, state),
                competency_codes_candidate=_extract_competency_codes(row_text),
                part_candidate=_detect_part(row_text, kind_cell, state.part),
                kind_cell=kind_cell,
            )
            candidates.append(candidate)
    return candidates


def _deduplicate_records(records: list[PoopDisciplineSeedRecord]) -> list[PoopDisciplineSeedRecord]:
    unique: dict[tuple, PoopDisciplineSeedRecord] = {}
    for record in records:
        key = (
            record.source_type,
            record.source_name,
            record.name,
            record.element_type,
            record.part,
            record.credits,
            tuple(record.semesters),
        )
        existing = unique.get(key)
        if existing is None:
            unique[key] = record
            continue
        merged_codes = existing.competency_codes.copy()
        for code in record.competency_codes:
            if code not in merged_codes:
                merged_codes.append(code)
        unique[key] = existing.model_copy(update={"competency_codes": merged_codes})
    return list(unique.values())


def _records_from_candidate_rows(
    candidate_rows: list[CandidateRow],
    *,
    direction_code: str,
) -> list[PoopDisciplineSeedRecord]:
    records: list[PoopDisciplineSeedRecord] = []
    for index, candidate in enumerate(candidate_rows, start=1):
        if candidate.credits_candidate is None:
            LOGGER.warning("Пропуск строки без трудоемкости: file=%s row=%s", candidate.source_name, index)
            continue

        practice_type = _detect_practice_type(candidate.name, row_id=candidate.row_id)
        element_type: Literal["discipline", "practice"] = "practice" if practice_type else "discipline"
        try:
            record = PoopDisciplineSeedRecord(
                direction_code=direction_code,
                source_name=candidate.source_name,
                source_type=candidate.source_type,
                name=candidate.name,
                element_type=element_type,
                part=candidate.part_candidate,
                credits=candidate.credits_candidate,
                semesters=candidate.semesters_candidate,
                competency_codes=candidate.competency_codes_candidate,
                practice_type=practice_type if element_type == "practice" else None,
                fgos_mandatory=_detect_fgos_mandatory(candidate.name) if element_type == "discipline" else None,
            )
        except Exception as exc:
            LOGGER.warning("Пропуск candidate row из-за ошибки валидации: file=%s row=%s error=%s", candidate.source_name, index, exc)
            continue
        records.append(record)
    return _deduplicate_records(records)


def _score_quality(
    records: list[PoopDisciplineSeedRecord],
    candidate_rows: list[CandidateRow],
    *,
    extractor_used: Literal["pymupdf", "docling", "pypdf", "text", "none"] = "none",
) -> tuple[float, bool]:
    if not records:
        return 0.0, True

    source_type = records[0].source_type if records else "poop"
    score = 1.0
    missing_semesters = sum(1 for record in records if not record.semesters)
    missing_competencies = sum(1 for record in records if not record.competency_codes)
    unique_names = len({(record.name, record.credits, tuple(record.semesters)) for record in records})
    duplicates = max(0, len(records) - unique_names)
    candidate_gap = max(0, len(candidate_rows) - len(records))
    practice_count = sum(1 for record in records if record.element_type == "practice")
    discipline_count = sum(1 for record in records if record.element_type == "discipline")

    semester_penalty = 0.35 if source_type == "poop" else 0.2
    competency_penalty = 0.25 if source_type == "poop" else 0.1

    score -= min(semester_penalty, missing_semesters / max(len(records), 1) * semester_penalty)
    score -= min(competency_penalty, missing_competencies / max(len(records), 1) * competency_penalty)
    score -= min(0.2, duplicates / max(len(records), 1) * 0.2)
    score -= min(0.2, candidate_gap / max(len(candidate_rows), 1) * 0.2) if candidate_rows else 0.0

    minimum_records = 5 if source_type == "poop" else 8
    if len(records) < minimum_records:
        score -= 0.15

    if not practice_count or not discipline_count:
        score -= 0.05

    if extractor_used == "text":
        empty_semester_ratio = missing_semesters / max(len(records), 1)
        if empty_semester_ratio >= 0.8:
            score -= 0.12
        if missing_competencies / max(len(records), 1) >= 0.5:
            score -= 0.08
    elif extractor_used in {"docling", "pypdf"}:
        if missing_semesters / max(len(records), 1) >= 0.8:
            score -= 0.08

    score = max(0.0, round(score, 3))
    review_threshold = 0.6 if source_type == "poop" else 0.5
    if extractor_used == "text":
        review_threshold += 0.05
    needs_review = score < review_threshold or len(records) < 3
    return score, needs_review


def _build_candidate_rows_context(candidate_rows: list[CandidateRow]) -> str:
    if not candidate_rows:
        return ""
    lines: list[str] = []
    for candidate in candidate_rows[:80]:
        lines.append(
            json.dumps(
                {
                    "page": candidate.page_number,
                    "extractor": candidate.extractor,
                    "row_id": candidate.row_id,
                    "name": candidate.name,
                    "credits_candidate": candidate.credits_candidate,
                    "semesters_candidate": candidate.semesters_candidate,
                    "competency_codes_candidate": candidate.competency_codes_candidate,
                    "part_candidate": candidate.part_candidate,
                    "cells": candidate.cells[:12],
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def _plan_sections_to_text(pdf_path: Path) -> str:
    sections = _extract_plan_section_texts(pdf_path)
    if not sections:
        return ""
    chunks: list[str] = []
    for page_number, text in sections:
        normalized = _normalize_cell(text)
        if not normalized:
            continue
        chunks.append(f"[page {page_number}]")
        chunks.append(normalized[:6000])
    return "\n\n".join(chunks).strip()


def _build_report_entry(
    *,
    pdf_path: Path,
    source_type: Literal["poop", "best_practices"],
    analysis: FileAnalysis,
) -> ImportReportEntry:
    direction_match = re.match(r"^(\d{6})", pdf_path.name)
    direction_code = direction_match.group(1) if direction_match else "000000"
    return ImportReportEntry(
        direction_code=direction_code,
        source_name=pdf_path.name,
        source_type=source_type,
        strategy_used=analysis.strategy_used,
        extractor_used=analysis.extractor_used,
        candidate_row_count=len(analysis.candidate_rows),
        record_count=len(analysis.records),
        quality_score=analysis.quality_score,
        needs_review=analysis.needs_review,
        warnings=analysis.warnings,
        candidate_samples=[asdict(candidate) for candidate in analysis.candidate_rows[:5]],
    )


def _build_manifest_entry(
    *,
    pdf_path: Path,
    source_type: Literal["poop", "best_practices"],
    analysis: FileAnalysis,
) -> ImportManifestEntry:
    return ImportManifestEntry(
        source_name=pdf_path.name,
        source_type=source_type,
        file_size_bytes=pdf_path.stat().st_size,
        sha256=hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        strategy_used=analysis.strategy_used,
        extractor_used=analysis.extractor_used,
        record_count=len(analysis.records),
        quality_score=analysis.quality_score,
        needs_review=analysis.needs_review,
    )


def _write_review_dump(
    *,
    pdf_path: Path,
    source_type: Literal["poop", "best_practices"],
    analysis: FileAnalysis,
    review_dir: Path,
) -> None:
    review_dir.mkdir(parents=True, exist_ok=True)
    review_payload = {
        "source_name": pdf_path.name,
        "source_type": source_type,
        "strategy_used": analysis.strategy_used,
        "extractor_used": analysis.extractor_used,
        "quality_score": analysis.quality_score,
        "needs_review": analysis.needs_review,
        "warnings": analysis.warnings,
        "candidate_row_count": len(analysis.candidate_rows),
        "record_count": len(analysis.records),
        "candidate_rows": [asdict(candidate) for candidate in analysis.candidate_rows],
        "records": [record.model_dump(mode="json") for record in analysis.records],
        "plan_sections": [
            {"page_number": page_number, "text": text[:8000]}
            for page_number, text in _extract_plan_section_texts(pdf_path)
        ],
    }
    review_path = review_dir / f"{pdf_path.stem}.review.json"
    review_path.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _blocks_to_text(blocks: list[TableBlock]) -> str:
    chunks: list[str] = []
    for block in blocks:
        row_lines = [" | ".join(cell for cell in row if cell) for row in block.rows if any(row)]
        if not row_lines:
            continue
        chunks.append(f"[page {block.page_number}]")
        chunks.append("\n".join(row_lines))
    return "\n\n".join(chunks).strip()


def _analyze_pdf_deterministically(
    pdf_path: Path,
    source_type: Literal["poop", "best_practices"] = "poop",
) -> FileAnalysis:
    direction_match = re.match(r"^(\d{6})", pdf_path.name)
    if direction_match is None:
        raise ValueError(f"Имя файла должно начинаться с 6 цифр: {pdf_path.name}")
    direction_code = direction_match.group(1)

    warnings: list[str] = []
    extractor_used: Literal["pymupdf", "docling", "pypdf", "text", "none"] = "none"

    blocks = _extract_table_blocks_with_pymupdf(pdf_path)
    candidate_rows = _extract_candidate_rows_from_blocks(blocks, source_name=pdf_path.name, source_type=source_type)
    if candidate_rows:
        extractor_used = "pymupdf"
    else:
        plan_sections = _extract_plan_section_texts(pdf_path)
        if not plan_sections and not _pdf_contains_plan_markers(pdf_path):
            warnings.append("no_plan_markers_detected")
            return FileAnalysis(
                records=[],
                candidate_rows=[],
                extractor_used="none",
                quality_score=0.0,
                needs_review=True,
                warnings=warnings,
                strategy_used="deterministic",
            )

        docling_blocks, docling_warnings = _extract_table_blocks_with_docling(pdf_path)
        warnings.extend(docling_warnings)
        candidate_rows = _extract_candidate_rows_from_blocks(docling_blocks, source_name=pdf_path.name, source_type=source_type)
        if candidate_rows:
            extractor_used = "docling"
        else:
            pypdf_blocks, pypdf_warnings = _extract_table_blocks_with_pypdf(pdf_path)
            warnings.extend(pypdf_warnings)
            candidate_rows = _extract_candidate_rows_from_blocks(pypdf_blocks, source_name=pdf_path.name, source_type=source_type)
            if candidate_rows:
                extractor_used = "pypdf"
            else:
                candidate_rows = _extract_candidate_rows_from_text_sections(pdf_path, source_name=pdf_path.name, source_type=source_type)
                if candidate_rows:
                    extractor_used = "text"

    records = _records_from_candidate_rows(candidate_rows, direction_code=direction_code)
    quality_score, needs_review = _score_quality(records, candidate_rows, extractor_used=extractor_used)

    if not records:
        warnings.append("no_records_extracted")
    elif extractor_used in {"docling", "pypdf", "text"}:
        warnings.append(f"used_{extractor_used}_fallback")

    return FileAnalysis(
        records=records,
        candidate_rows=candidate_rows,
        extractor_used=extractor_used,
        quality_score=quality_score,
        needs_review=needs_review,
        warnings=warnings,
        strategy_used="deterministic",
    )


def extract_records_from_pdf(
    pdf_path: Path,
    source_type: Literal["poop", "best_practices"] = "poop",
) -> list[PoopDisciplineSeedRecord]:
    return _analyze_pdf_deterministically(pdf_path, source_type=source_type).records


def _analyze_pdf(
    pdf_path: Path,
    *,
    source_type: Literal["poop", "best_practices"],
    strategy: Literal["deterministic"],
) -> FileAnalysis:
    deterministic = _analyze_pdf_deterministically(pdf_path, source_type=source_type)
    deterministic.strategy_used = "deterministic"
    return deterministic


def import_poops_from_directory(
    input_dir: Path,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    strategy: Literal["deterministic"] = "deterministic",
    source_type: Literal["poop", "best_practices"] = "poop",
    persist_output: bool = True,
    report_path: Path | None = None,
    manifest_path: Path | None = DEFAULT_MANIFEST_PATH,
    review_dir: Path | None = DEFAULT_REVIEW_DIR,
) -> list[PoopDisciplineSeedRecord]:
    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"В папке не найдены PDF-файлы: {input_dir}")

    all_records: list[PoopDisciplineSeedRecord] = []
    reports: list[ImportReportEntry] = []
    manifests: list[ImportManifestEntry] = []
    for pdf_path in pdf_files:
        analysis = _analyze_pdf(pdf_path, source_type=source_type, strategy=strategy)
        if not analysis.records:
            LOGGER.warning("В PDF не найдено пригодных строк учебного плана: %s", pdf_path.name)
        if analysis.needs_review:
            LOGGER.warning("Файл требует проверки: %s quality_score=%s", pdf_path.name, analysis.quality_score)
            if review_dir is not None:
                _write_review_dump(pdf_path=pdf_path, source_type=source_type, analysis=analysis, review_dir=review_dir)
        LOGGER.info("Обработан PDF: %s, записей=%s extractor=%s", pdf_path.name, len(analysis.records), analysis.extractor_used)
        all_records.extend(analysis.records)
        reports.append(_build_report_entry(pdf_path=pdf_path, source_type=source_type, analysis=analysis))
        manifests.append(_build_manifest_entry(pdf_path=pdf_path, source_type=source_type, analysis=analysis))

    if persist_output:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([record.model_dump(mode="json") for record in all_records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if report_path is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps([entry.model_dump(mode="json") for entry in reports], ensure_ascii=False, indent=2), encoding="utf-8")
        if manifest_path is not None:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps([entry.model_dump(mode="json") for entry in manifests], ensure_ascii=False, indent=2), encoding="utf-8")
    return all_records


def import_seed_sources(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    strategy: Literal["deterministic"] = "deterministic",
    source_types: tuple[Literal["poop", "best_practices"], ...] = ("poop", "best_practices"),
    source_dirs: dict[Literal["poop", "best_practices"], Path] | None = None,
    report_path: Path = DEFAULT_REPORT_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    review_dir: Path | None = DEFAULT_REVIEW_DIR,
) -> list[PoopDisciplineSeedRecord]:
    all_records: list[PoopDisciplineSeedRecord] = []
    all_reports: list[ImportReportEntry] = []
    all_manifests: list[ImportManifestEntry] = []

    for source_type in source_types:
        source_config = _get_source_config(source_type)
        input_dir = (source_dirs or {}).get(source_type, source_config.input_dir)
        if not input_dir.exists():
            LOGGER.warning("Папка источника не найдена, пропуск: %s", input_dir)
            continue

        pdf_files = sorted(input_dir.glob("*.pdf"))
        for pdf_path in pdf_files:
            analysis = _analyze_pdf(pdf_path, source_type=source_type, strategy=strategy)
            if not analysis.records:
                LOGGER.warning("В PDF не найдено пригодных строк учебного плана: %s", pdf_path.name)
            if analysis.needs_review:
                LOGGER.warning("Файл требует проверки: %s quality_score=%s", pdf_path.name, analysis.quality_score)
                if review_dir is not None:
                    _write_review_dump(pdf_path=pdf_path, source_type=source_type, analysis=analysis, review_dir=review_dir)
            LOGGER.info("Обработан PDF: %s, записей=%s extractor=%s", pdf_path.name, len(analysis.records), analysis.extractor_used)
            all_records.extend(analysis.records)
            all_reports.append(_build_report_entry(pdf_path=pdf_path, source_type=source_type, analysis=analysis))
            all_manifests.append(_build_manifest_entry(pdf_path=pdf_path, source_type=source_type, analysis=analysis))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([record.model_dump(mode="json") for record in all_records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps([entry.model_dump(mode="json") for entry in all_reports], ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps([entry.model_dump(mode="json") for entry in all_manifests], ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("Сохранен объединенный JSON: %s, записей=%s", output_path, len(all_records))
    LOGGER.info("Сохранен отчет импорта: %s, файлов=%s", report_path, len(all_reports))
    return all_records

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Универсальный импорт ПООП и лучших практик из PDF в JSON seed-файл.")
    parser.add_argument("--poop-dir", type=Path, default=DEFAULT_POOP_DIR, help=f"Папка с PDF-файлами ПООП. По умолчанию: {DEFAULT_POOP_DIR}")
    parser.add_argument("--best-practices-dir", type=Path, default=DEFAULT_BEST_PRACTICES_DIR, help=f"Папка с PDF-файлами лучших практик. По умолчанию: {DEFAULT_BEST_PRACTICES_DIR}")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help=f"Куда сохранить итоговый JSON. По умолчанию: {DEFAULT_OUTPUT_PATH}")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH, help=f"Куда сохранить отчет импорта. По умолчанию: {DEFAULT_REPORT_PATH}")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH, help=f"Куда сохранить import manifest. По умолчанию: {DEFAULT_MANIFEST_PATH}")
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR, help=f"Папка для review-dump. По умолчанию: {DEFAULT_REVIEW_DIR}")
    parser.add_argument("--strategy", default="deterministic", choices=IMPORT_STRATEGIES, help="Режим импорта: deterministic.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Уровень логирования.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(name)s: %(message)s")
    import_seed_sources(
        output_path=args.output,
        strategy=args.strategy,
        source_dirs={"poop": args.poop_dir, "best_practices": args.best_practices_dir},
        report_path=args.report,
        manifest_path=args.manifest,
        review_dir=args.review_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
