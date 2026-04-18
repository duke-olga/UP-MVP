from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import fitz
from pydantic import BaseModel, Field

from backend.modules.llm_explainer.adapter import LLMAdapterError, OllamaAdapter


LOGGER = logging.getLogger(__name__)

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
DEFAULT_POOP_DIR = SEED_DIR / "poop_pdf"
DEFAULT_BEST_PRACTICES_DIR = SEED_DIR / "best_practices_pdf"
DEFAULT_OUTPUT_PATH = SEED_DIR / "poop_disciplines.json"
IMPORT_STRATEGIES = ("deterministic", "hybrid", "llm")

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


@dataclass(frozen=True)
class SeedSourceConfig:
    source_type: Literal["poop", "best_practices"]
    input_dir: Path
    llm_context_label: str
    llm_prompt_hint: str


@dataclass
class TableBlock:
    page_number: int
    rows: list[list[str]]
    page_text: str


@dataclass
class ParserState:
    part: Literal["mandatory", "variative"] = "mandatory"
    current_group: str = ""
    semester_columns: dict[int, int] = field(default_factory=dict)
    first_column_is_semester: bool = False


SOURCE_CONFIGS: tuple[SeedSourceConfig, ...] = (
    SeedSourceConfig(
        source_type="poop",
        input_dir=DEFAULT_POOP_DIR,
        llm_context_label="ПООП",
        llm_prompt_hint=(
            "Извлекай только реальные элементы учебного плана из табличной части документа. "
            "Игнорируй пояснения, агрегаты по блокам, календарный график и описания компетенций."
        ),
    ),
    SeedSourceConfig(
        source_type="best_practices",
        input_dir=DEFAULT_BEST_PRACTICES_DIR,
        llm_context_label="Лучшие практики",
        llm_prompt_hint=(
            "Это учебный план другого вуза. Извлекай только дисциплины и практики из таблиц учебного плана. "
            "Игнорируй подписи, агрегаты и матрицы компетенций."
        ),
    ),
)
SOURCE_CONFIG_MAP = {config.source_type: config for config in SOURCE_CONFIGS}


LLM_SYSTEM_PROMPT = """
Ты извлекаешь из текста PDF только элементы учебного плана и возвращаешь только JSON-массив.
Без Markdown, без пояснений, без дополнительных полей.

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

Правила:
- part="mandatory" для обязательной/базовой части и строк с типом "О";
- part="variative" для вариативной части, строк "по выбору", факультативов и строк с типом "В" или "Ф";
- element_type="practice" только если название явно относится к практике;
- practice_type="educational" только для учебной практики;
- practice_type="industrial" для производственной, технологической, эксплуатационной, преддипломной и похожих практик;
- если семестры не указаны надежно, возвращай [];
- competency_codes содержат только коды компетенций;
- если поле нельзя определить надежно, используй null или [].
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


def _parse_credits(raw_value: str, source_name: str, row_number: int) -> float | None:
    value = _parse_float(raw_value)
    if value is None:
        LOGGER.warning("Пропуск строки без трудоемкости: file=%s row=%s value=%r", source_name, row_number, raw_value)
        return None
    return value


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


def _find_credit_candidates(cells: list[str]) -> list[float]:
    values: list[float] = []
    for cell in cells:
        value = _parse_float(cell)
        if value is None:
            continue
        if 0 < value <= 60:
            values.append(value)
    return values


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


def _extract_table_blocks(pdf_path: Path) -> list[TableBlock]:
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
                    page_blocks.append(TableBlock(page_number=page_index + 1, rows=rows, page_text=page_text))
                    continue
                if in_plan_section and _table_looks_like_continuation(page_text, rows):
                    page_blocks.append(TableBlock(page_number=page_index + 1, rows=rows, page_text=page_text))

            if page_blocks:
                blocks.extend(page_blocks)
                in_plan_section = True
                continue

            if in_plan_section and any(marker in page_text.casefold() for marker in STOP_HINTS):
                break

    return blocks


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
            semester_columns = {index: semester for index, semester in zip(range(4, 12), range(1, 9), strict=False)}

    return semester_columns, first_column_is_semester


def _update_state_from_summary(row_text: str, state: ParserState) -> bool:
    lowered = row_text.casefold()
    state.part = _detect_part(row_text, None, state.part)
    if any(marker in lowered for marker in SUMMARY_HINTS):
        state.current_group = row_text
        return True
    return False


def _should_skip_name(name: str) -> bool:
    lowered = name.casefold()
    if not _looks_like_candidate_name(name):
        return True
    if _is_summary_name(name):
        return True
    if any(marker in lowered for marker in IGNORE_NAME_HINTS):
        return True
    return False


def _parse_generic_row(
    *,
    direction_code: str,
    source_name: str,
    source_type: Literal["poop", "best_practices"],
    row_number: int,
    row: list[str],
    state: ParserState,
) -> PoopDisciplineSeedRecord | None:
    row_text = " ".join(cell for cell in row if cell)
    if not row_text:
        return None
    if _update_state_from_summary(row_text, state):
        return None

    nonempty = [cell for cell in row if cell]
    if len(nonempty) < 2 or not _looks_like_row_identifier(nonempty[0]):
        return None

    row_id = nonempty[0]
    name, tail_cells, kind_cell = _extract_name_and_tail(row)
    if _should_skip_name(name):
        return None

    competency_codes = _extract_competency_codes(row_text)
    semesters = _extract_semesters_from_row(row, state)
    if not competency_codes and not kind_cell and not semesters and len(name.split()) <= 2:
        return None

    credit_candidates = _find_credit_candidates(tail_cells or row)
    if not credit_candidates:
        return None

    credits = _parse_credits(str(credit_candidates[0]), source_name, row_number)
    if credits is None:
        return None

    part = _detect_part(row_text, kind_cell, state.part)
    practice_type = _detect_practice_type(name, row_id=row_id)
    element_type: Literal["discipline", "practice"] = "practice" if practice_type else "discipline"

    return PoopDisciplineSeedRecord(
        direction_code=direction_code,
        source_name=source_name,
        source_type=source_type,
        name=name,
        element_type=element_type,
        part=part,
        credits=credits,
        semesters=semesters,
        competency_codes=competency_codes,
        practice_type=practice_type if element_type == "practice" else None,
        fgos_mandatory=_detect_fgos_mandatory(name) if element_type == "discipline" else None,
    )


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


def _extract_relevant_text(pdf_path: Path) -> str:
    blocks = _extract_table_blocks(pdf_path)
    if not blocks:
        with fitz.open(pdf_path) as document:
            pages = [document.load_page(index).get_text("text") for index in range(document.page_count)]
        return "\n\n".join(pages).strip()[:60000]

    chunks: list[str] = []
    for block in blocks:
        row_lines = [" | ".join(cell for cell in row if cell) for row in block.rows if any(row)]
        if not row_lines:
            continue
        chunks.append(f"[page {block.page_number}]")
        chunks.append("\n".join(row_lines))
    return "\n\n".join(chunks).strip()


def _build_llm_prompt(
    direction_code: str,
    source_name: str,
    source_type: Literal["poop", "best_practices"],
    relevant_text: str,
) -> str:
    source_config = _get_source_config(source_type)
    return f"""
Извлеки элементы учебного плана из текста документа.

Контекст:
- direction_code: {direction_code}
- source_name: {source_name}
- source_type: {source_type}
- document_kind: {source_config.llm_context_label}

Инструкция:
{source_config.llm_prompt_hint}

Текст:
{relevant_text}
""".strip()


def extract_records_from_pdf_with_llm(
    pdf_path: Path,
    source_type: Literal["poop", "best_practices"] = "poop",
    adapter: OllamaAdapter | None = None,
) -> list[PoopDisciplineSeedRecord]:
    direction_match = re.match(r"^(\d{6})", pdf_path.name)
    if direction_match is None:
        raise ValueError(f"Имя файла должно начинаться с 6 цифр: {pdf_path.name}")

    direction_code = direction_match.group(1)
    relevant_text = _extract_relevant_text(pdf_path)
    if not relevant_text:
        LOGGER.warning("Для LLM-извлечения не найден пригодный текст: file=%s source_type=%s", pdf_path.name, source_type)
        return []

    active_adapter = adapter or OllamaAdapter()
    response = active_adapter.generate(
        prompt=_build_llm_prompt(direction_code, pdf_path.name, source_type, relevant_text),
        system_prompt=LLM_SYSTEM_PROMPT,
    )

    raw_items = _extract_json_array(response)
    records: list[PoopDisciplineSeedRecord] = []
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            LOGGER.warning("Пропуск невалидного объекта LLM: file=%s item=%s type=%s", pdf_path.name, index, type(item).__name__)
            continue
        try:
            record = PoopDisciplineSeedRecord(
                direction_code=direction_code,
                source_name=pdf_path.name,
                source_type=source_type,
                name=_normalize_name(str(item.get("name", ""))),
                element_type=item.get("element_type"),
                part=item.get("part"),
                credits=item.get("credits"),
                semesters=item.get("semesters") or [],
                competency_codes=item.get("competency_codes") or [],
                practice_type=item.get("practice_type"),
                fgos_mandatory=item.get("fgos_mandatory"),
            )
        except Exception as exc:
            LOGGER.warning("Пропуск строки из LLM из-за ошибки валидации: file=%s item=%s error=%s", pdf_path.name, index, exc)
            continue
        if _should_skip_name(record.name):
            LOGGER.warning("Пропуск агрегированной LLM-строки: file=%s item=%s name=%r", pdf_path.name, index, record.name)
            continue
        records.append(record)

    return _deduplicate_records(records)


def extract_records_from_pdf(
    pdf_path: Path,
    source_type: Literal["poop", "best_practices"] = "poop",
) -> list[PoopDisciplineSeedRecord]:
    direction_match = re.match(r"^(\d{6})", pdf_path.name)
    if direction_match is None:
        raise ValueError(f"Имя файла должно начинаться с 6 цифр: {pdf_path.name}")

    direction_code = direction_match.group(1)
    blocks = _extract_table_blocks(pdf_path)
    records: list[PoopDisciplineSeedRecord] = []

    for block in blocks:
        semester_columns, first_column_is_semester = _infer_semester_columns(block.rows)
        state = ParserState(semester_columns=semester_columns, first_column_is_semester=first_column_is_semester)
        for row_number, row in enumerate(block.rows, start=1):
            record = _parse_generic_row(
                direction_code=direction_code,
                source_name=pdf_path.name,
                source_type=source_type,
                row_number=row_number,
                row=row,
                state=state,
            )
            if record is not None:
                records.append(record)

    return _deduplicate_records(records)


def import_poops_from_directory(
    input_dir: Path,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    strategy: Literal["deterministic", "hybrid", "llm"] = "hybrid",
    source_type: Literal["poop", "best_practices"] = "poop",
    adapter: OllamaAdapter | None = None,
    persist_output: bool = True,
) -> list[PoopDisciplineSeedRecord]:
    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"В папке не найдены PDF-файлы: {input_dir}")

    all_records: list[PoopDisciplineSeedRecord] = []
    for pdf_path in pdf_files:
        if strategy == "deterministic":
            file_records = extract_records_from_pdf(pdf_path, source_type=source_type)
        elif strategy == "llm":
            try:
                file_records = extract_records_from_pdf_with_llm(pdf_path, source_type=source_type, adapter=adapter)
            except (LLMAdapterError, ValueError, json.JSONDecodeError) as exc:
                LOGGER.warning("LLM-извлечение завершилось ошибкой: file=%s error=%s", pdf_path.name, exc)
                file_records = []
        else:
            file_records = extract_records_from_pdf(pdf_path, source_type=source_type)
            if not file_records:
                try:
                    file_records = extract_records_from_pdf_with_llm(pdf_path, source_type=source_type, adapter=adapter)
                except (LLMAdapterError, ValueError, json.JSONDecodeError) as exc:
                    LOGGER.warning("LLM fallback завершился ошибкой, остается детерминированный результат: file=%s error=%s", pdf_path.name, exc)

        if not file_records:
            LOGGER.warning("В PDF не найдено пригодных строк учебного плана: %s", pdf_path.name)
        LOGGER.info("Обработан PDF: %s, записей=%s", pdf_path.name, len(file_records))
        all_records.extend(file_records)

    if persist_output:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([record.model_dump(mode="json") for record in all_records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        LOGGER.info("Сохранен JSON: %s, записей=%s", output_path, len(all_records))
    return all_records


def import_seed_sources(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    strategy: Literal["deterministic", "hybrid", "llm"] = "hybrid",
    adapter: OllamaAdapter | None = None,
    source_types: tuple[Literal["poop", "best_practices"], ...] = ("poop", "best_practices"),
    source_dirs: dict[Literal["poop", "best_practices"], Path] | None = None,
) -> list[PoopDisciplineSeedRecord]:
    all_records: list[PoopDisciplineSeedRecord] = []
    for source_type in source_types:
        source_config = _get_source_config(source_type)
        input_dir = (source_dirs or {}).get(source_type, source_config.input_dir)
        if not input_dir.exists():
            LOGGER.warning("Папка источника не найдена, пропуск: %s", input_dir)
            continue
        all_records.extend(
            import_poops_from_directory(
                input_dir=input_dir,
                output_path=output_path,
                strategy=strategy,
                source_type=source_type,
                adapter=adapter,
                persist_output=False,
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([record.model_dump(mode="json") for record in all_records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    LOGGER.info("Сохранен объединенный JSON: %s, записей=%s", output_path, len(all_records))
    return all_records


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Универсальный импорт ПООП и лучших практик из PDF в JSON seed-файл.")
    parser.add_argument("--poop-dir", type=Path, default=DEFAULT_POOP_DIR, help=f"Папка с PDF-файлами ПООП. По умолчанию: {DEFAULT_POOP_DIR}")
    parser.add_argument(
        "--best-practices-dir",
        type=Path,
        default=DEFAULT_BEST_PRACTICES_DIR,
        help=f"Папка с PDF-файлами лучших практик. По умолчанию: {DEFAULT_BEST_PRACTICES_DIR}",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help=f"Куда сохранить итоговый JSON. По умолчанию: {DEFAULT_OUTPUT_PATH}")
    parser.add_argument("--strategy", default="hybrid", choices=IMPORT_STRATEGIES, help="Режим импорта: deterministic | hybrid | llm.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Уровень логирования.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(name)s: %(message)s")
    import_seed_sources(
        output_path=args.output,
        strategy=args.strategy,
        source_dirs={
            "poop": args.poop_dir,
            "best_practices": args.best_practices_dir,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
