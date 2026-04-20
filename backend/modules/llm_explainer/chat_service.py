from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models import CheckReport, Competency, CurriculumPlan, NormativeParam, PlanElement
from backend.modules.llm_explainer.adapter import LLMAdapterError, OllamaAdapter
from backend.modules.plan_builder.calculator import (
    aggregate_by_block,
    aggregate_by_semester,
    aggregate_mandatory_percent,
    get_competency_coverage,
)

_SYSTEM_PROMPT = """\
Ты — ИИ-ассистент методиста вуза по проектированию учебных планов ОПОП/ФГОС.
У тебя есть доступ к текущей структуре учебного плана (см. контекст ниже).

Отвечай ТОЛЬКО на вопросы, связанные с проектированием учебных планов:
размещение дисциплин по семестрам, нагрузка, компетенции, нормативы ФГОС,
структура блоков, соотношение обязательной и вариативной частей.

Если вопрос не относится к учебным планам и образовательным программам —
вежливо объясни, что ты помогаешь только с проектированием ОПОП.

Отвечай на русском языке. Будь конкретным и практичным.
Не выдумывай данные, которых нет в контексте. Опирайся на предоставленный план.\
"""

_BLOCK_NAMES = {"1": "Блок 1 (Дисциплины)", "2": "Блок 2 (Практики)", "3": "Блок 3 (ГИА)", "fac": "Факультативные"}
_PART_NAMES = {"mandatory": "обязательная", "variative": "вариативная"}


def _get_norms(db: Session) -> dict[str, float]:
    rows = db.query(NormativeParam).all()
    return {r.key: r.value for r in rows}


def build_plan_context(plan_id: int, db: Session) -> str:
    plan = db.query(CurriculumPlan).filter(CurriculumPlan.id == plan_id).first()
    if plan is None:
        return "План не найден."

    elements = db.query(PlanElement).filter(PlanElement.plan_id == plan_id).all()
    competencies = db.query(Competency).all()
    norms = _get_norms(db)

    by_block = aggregate_by_block(elements)
    by_sem = aggregate_by_semester(elements)
    mand_pct = aggregate_mandatory_percent(elements)
    coverage = get_competency_coverage(elements, competencies)

    total_credits = sum(by_block.values())

    lines: list[str] = []
    lines.append(f"=== УЧЕБНЫЙ ПЛАН: «{plan.name}» ===")
    lines.append(f"Программа: {plan.program_code}, Статус: {plan.status}")
    lines.append(f"Всего зачётных единиц: {total_credits:.1f} (норматив: {norms.get('X_total', 240):.0f} з.е.)")
    lines.append(
        f"Обязательная часть: {mand_pct * 100:.1f}% (норматив: ≥{norms.get('X_mandatory_percent', 0.4) * 100:.0f}%)"
    )

    lines.append("\n--- Нагрузка по блокам ---")
    for block, credits in sorted(by_block.items()):
        name = _BLOCK_NAMES.get(block, f"Блок {block}")
        lines.append(f"  {name}: {credits:.1f} з.е.")

    if by_sem:
        lines.append("\n--- Нагрузка по семестрам ---")
        sem_max = norms.get("X_semester_max", 35)
        for sem in sorted(by_sem.keys()):
            flag = " ⚠ превышение" if by_sem[sem] > sem_max else ""
            lines.append(f"  Семестр {sem}: {by_sem[sem]:.1f} з.е.{flag}")

    lines.append(f"\n--- Дисциплины и практики ({len(elements)} эл.) ---")
    for el in sorted(elements, key=lambda e: (e.block, e.part, e.name)):
        block_label = _BLOCK_NAMES.get(el.block, el.block)
        part_label = _PART_NAMES.get(el.part, el.part)
        sems = ", ".join(str(s) for s in (el.semesters or []))
        comp_codes = []
        if el.competency_ids:
            id_set = set(el.competency_ids)
            comp_codes = [c.code for c in competencies if c.id in id_set]
        comp_str = f" [{', '.join(comp_codes)}]" if comp_codes else ""
        lines.append(
            f"  • {el.name} | {block_label}, {part_label} | "
            f"{el.credits:.1f} з.е. | сем.: {sems or '—'}{comp_str}"
        )

    uncovered = [code for code, ok in coverage.items() if not ok]
    if uncovered:
        lines.append(f"\n⚠ Компетенции без дисциплин: {', '.join(sorted(uncovered))}")
    else:
        lines.append(f"\n✓ Все {len(coverage)} компетенций покрыты.")

    latest_report = (
        db.query(CheckReport)
        .filter(CheckReport.plan_id == plan_id)
        .order_by(CheckReport.created_at.desc())
        .first()
    )
    if latest_report and latest_report.results:
        lines.append("\n--- Последние нарушения (из отчёта проверки) ---")
        for issue in latest_report.results:
            lines.append(
                f"  [{issue.get('level', '?').upper()}] {issue.get('message', '')} "
                f"(факт: {issue.get('actual')}, ожидалось: {issue.get('expected')})"
            )

    lines.append("\n--- Нормативные параметры ---")
    for key, val in sorted(norms.items()):
        lines.append(f"  {key}: {val}")

    return "\n".join(lines)


def chat_with_plan(
    plan_id: int,
    user_message: str,
    db: Session,
    adapter: OllamaAdapter | None = None,
) -> str:
    if adapter is None:
        adapter = OllamaAdapter()

    context = build_plan_context(plan_id, db)
    user_prompt = f"{context}\n\n=== ВОПРОС ПОЛЬЗОВАТЕЛЯ ===\n{user_message}"

    try:
        return adapter.generate(prompt=user_prompt, system_prompt=_SYSTEM_PROMPT)
    except LLMAdapterError as exc:
        return (
            f"ИИ-ассистент временно недоступен (Ollama не запущен или не отвечает).\n"
            f"Техническая причина: {exc}"
        )
