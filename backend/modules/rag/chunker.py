from __future__ import annotations

from dataclasses import dataclass

from backend.models import Competency, RecommendedElement

_SOURCE_LABELS: dict[str, str] = {
    "poop": "ПООП",
    "best_practices": "Лучшие практики",
    "best_practice": "Лучшие практики",
    "local_requirement": "Локальные требования",
    "local": "Локальные требования",
}
_PRACTICE_TYPES: dict[str, str] = {
    "educational": "учебная",
    "industrial": "производственная",
}


@dataclass
class Chunk:
    text: str
    source_type: str   # "element" | "competency"
    source_label: str  # human-readable label for citation


def _source_label(source: str) -> str:
    return _SOURCE_LABELS.get(source, source)


def build_chunks(
    program_code: str,
    elements: list[RecommendedElement],
    competencies: list[Competency],
) -> list[Chunk]:
    chunks: list[Chunk] = []

    # --- Competency chunks ---
    for comp in competencies:
        text = f"{comp.code} ({comp.type}): {comp.name}. {comp.description or ''}".strip()
        chunks.append(Chunk(text=text, source_type="competency", source_label=f"Компетенция {comp.code}"))

    # --- Recommended element chunks (filtered to program_code) ---
    for el in elements:
        comp_codes = sorted(c.code for c in (el.competencies or []))
        src = _source_label(el.source)
        sems = ", ".join(str(s) for s in sorted(el.semesters or []))
        comp_str = f" Формирует компетенции: {', '.join(comp_codes)}." if comp_codes else ""
        fgos_note = " [ФГОС обязательная]" if el.is_fgos_mandatory else ""

        if el.element_type == "discipline":
            part_label = "обязательная часть" if el.part == "mandatory" else "вариативная часть"
            text = (
                f"Дисциплина{fgos_note} направления {program_code}: «{el.name}». "
                f"Блок 1, {part_label}. "
                f"Кредиты: {el.credits or '?'} з.е. "
                f"Семестры: {sems or 'не указаны'}. "
                f"Источник: {src}.{comp_str}"
            )
        else:
            ptype = _PRACTICE_TYPES.get(el.practice_type or "", el.practice_type or "практика")
            text = (
                f"Практика{fgos_note} направления {program_code}: «{el.name}». "
                f"Тип: {ptype}. "
                f"Кредиты: {el.credits or '?'} з.е. "
                f"Семестры: {sems or 'не указаны'}. "
                f"Источник: {src}.{comp_str}"
            )

        chunks.append(Chunk(text=text, source_type="element", source_label=f"{src}: {el.name}"))

    return chunks
