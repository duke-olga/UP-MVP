from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from backend.models import Competency, RecommendedElement

_TYPE_FULL_NAMES: dict[str, str] = {
    "УК": "универсальные компетенции",
    "ОПК": "общепрофессиональные компетенции",
    "ПК": "профессиональные компетенции",
}

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
    norms: dict[str, float] | None = None,
) -> list[Chunk]:
    chunks: list[Chunk] = []

    # --- Synthetic normative block-volume chunk ---
    # Added first so it gets high retrieval priority for min-volume queries.
    if norms:
        b1 = norms.get("X_b1", 160)
        b2 = norms.get("X_b2", 20)
        b3 = norms.get("X_b3", 9)
        total = norms.get("X_total", 240)
        sem_max = norms.get("X_semester_max", 35)
        text = (
            f"Нормативные объёмы блоков программы бакалавриата {program_code} по ФГОС ВО. "
            f"Минимальный объём блока 1 «Дисциплины (модули)» — не менее {b1:.0f} з.е. "
            f"Минимальный объём блока 2 «Практика» — не менее {b2:.0f} з.е. "
            f"Минимальный объём блока 3 «Государственная итоговая аттестация» — не менее {b3:.0f} з.е. "
            f"Общий объём программы — {total:.0f} зачётных единиц. "
            f"Максимальная нагрузка в семестр — не более {sem_max:.0f} з.е."
        )
        chunks.append(Chunk(
            text=text,
            source_type="fgos",
            source_label=f"ФГОС ВО {program_code}, нормативы объёмов блоков",
        ))

    # --- Aggregate competency-type chunks (one per type: УК, ОПК, ПК) ---
    # These score high for queries like "Какие ОПК перечислены в ФГОС?"
    by_type: dict[str, list[Competency]] = defaultdict(list)
    for comp in competencies:
        by_type[comp.type].append(comp)
    for ctype, comps in sorted(by_type.items()):
        full_name = _TYPE_FULL_NAMES.get(ctype, ctype)
        # Short aggregate: code + name only (no descriptions) so mean-pooled embedding
        # stays focused on the key terms and matches "list ОПК" queries.
        lines = [
            f"Перечень {ctype} ({full_name}) в ФГОС ВО для направления {program_code}:"
        ]
        for c in sorted(comps, key=lambda x: x.code):
            lines.append(f"{c.code}. {c.name}.")
        text = "\n".join(lines)
        chunks.append(Chunk(
            text=text,
            source_type="fgos",
            source_label=f"ФГОС ВО {program_code}, компетенции {ctype}",
        ))

    # --- Individual competency chunks (FGOS-authoritative content) ---
    # source_type="fgos" ensures they go into the FGOS retrieval pool where they
    # outcompete irrelevant PDF sections for competency-specific queries.
    for comp in competencies:
        text = f"{comp.code} ({comp.type}): {comp.name}. {comp.description or ''}".strip()
        chunks.append(Chunk(text=text, source_type="fgos", source_label=f"Компетенция {comp.code}"))

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
