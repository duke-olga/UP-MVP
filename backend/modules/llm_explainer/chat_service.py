from __future__ import annotations

import logging
from sqlalchemy.orm import Session, selectinload

_log = logging.getLogger(__name__)

from backend.models import CheckReport, Competency, CurriculumPlan, NormativeParam, PlanElement, RecommendedElement
from backend.modules.llm_explainer.adapter import LLMAdapterError, OllamaAdapter
from backend.modules.plan_builder.calculator import (
    aggregate_by_block,
    aggregate_by_semester,
    aggregate_mandatory_percent,
    get_competency_coverage,
)

_BLOCK_NAMES = {"1": "Блок 1 (Дисциплины)", "2": "Блок 2 (Практики)", "3": "Блок 3 (ГИА)", "fac": "Факультативные"}
_PART_NAMES = {"mandatory": "обязательная", "variative": "вариативная"}


def _build_system_prompt(program_code: str) -> str:
    return f"""\
Ты — методист-помощник по проектированию ОПОП/ФГОС для направления {program_code}.

В каждом запросе тебе предоставлены два источника:
— «НОРМАТИВНАЯ БАЗА» — фрагменты ФГОС ВО и нормативных документов (что должно быть).
— «УЧЕБНЫЙ ПЛАН» — текущее состояние проектируемого плана (что есть сейчас).

Правила:
1. Используй ТОЛЬКО информацию из этих разделов. Не добавляй знания из памяти.
2. Для вопросов о требованиях, нормативах, перечнях — опирайся прежде всего на «НОРМАТИВНАЯ БАЗА» и цитируй источник (номер пункта ФГОС).
3. Для вопросов об анализе плана, нарушениях, покрытии компетенций — используй оба источника.
4. Если нужной информации нет ни в одном из разделов — так и скажи.
5. Отвечай только по теме проектирования учебных планов. На посторонние вопросы вежливо откажи.

Отвечай на русском. Будь конкретным. Ссылайся на источник.\
"""


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
    lines.append(f"Направление: {plan.program_code} | Статус: {plan.status}")
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


def _build_rag_context(
    query: str,
    program_code: str,
    db: Session,
    top_k: int = 8,
) -> str:
    """Retrieves semantically relevant chunks from the knowledge base for this program_code.
    Returns empty string if the embedding model is unavailable or if retrieval fails."""
    try:
        from backend.modules.rag.retriever import retrieve  # noqa: PLC0415
        from backend.modules.recommendation.embedder import is_available  # noqa: PLC0415

        if not is_available():
            _log.warning("RAG: embedding model unavailable, skipping FGOS context")
            return ""

        elements = (
            db.query(RecommendedElement)
            .options(selectinload(RecommendedElement.competencies))
            .filter(RecommendedElement.program_code == program_code)
            .all()
        )
        competencies = (
            db.query(Competency)
            .order_by(Competency.type, Competency.code)
            .all()
        )

        norms = _get_norms(db)

        results = retrieve(
            query=query,
            program_code=program_code,
            elements=elements,
            competencies=competencies,
            top_k=top_k,
            norms=norms,
        )
        if not results:
            _log.info("RAG: no results for query=%r program=%s", query, program_code)
            return ""

        _log.info(
            "RAG: retrieved %d chunks for query=%r: %s",
            len(results),
            query,
            ", ".join(f"{r.chunk.source_label}({r.score:.2f})" for r in results),
        )

        lines: list[str] = [
            f"\n=== НОРМАТИВНАЯ БАЗА (направление {program_code}) ===",
            "Ниже приведены фрагменты нормативных документов, найденные по смыслу вопроса.",
            "Используй именно эту информацию для ответа.",
            "",
        ]
        for r in results:
            lines.append(f"[{r.chunk.source_label}]")
            lines.append(r.chunk.text)
            lines.append("")

        return "\n".join(lines)
    except Exception as exc:
        _log.warning("RAG context build failed, falling back to no-RAG mode: %s", exc, exc_info=True)
        return ""


def chat_with_plan(
    plan_id: int,
    user_message: str,
    db: Session,
    adapter: OllamaAdapter | None = None,
) -> str:
    if adapter is None:
        adapter = OllamaAdapter()

    plan = db.query(CurriculumPlan).filter(CurriculumPlan.id == plan_id).first()
    program_code = plan.program_code if plan else "не определено"

    plan_context = build_plan_context(plan_id, db)
    rag_context = _build_rag_context(user_message, program_code, db, top_k=10)

    # RAG context goes FIRST so the model attends to it (small models have "lost in the middle" problem).
    # Instruction is repeated at the very end (second-highest attention position).
    if rag_context:
        user_prompt = (
            f"{rag_context}\n\n"
            f"{plan_context}"
            f"\n\n=== ВОПРОС ===\n{user_message}"
            f"\n\n=== ВАЖНО ===\n"
            f"Ответь, опираясь на раздел «НОРМАТИВНАЯ БАЗА» выше. "
            f"Если там есть нужная информация — процитируй её точно с указанием пункта. "
            f"Не добавляй ничего от себя."
        )
    else:
        user_prompt = (
            f"{plan_context}"
            f"\n\n=== ВОПРОС ===\n{user_message}"
        )

    try:
        return adapter.generate(prompt=user_prompt, system_prompt=_build_system_prompt(program_code))
    except LLMAdapterError as exc:
        return (
            f"ИИ-ассистент временно недоступен (Ollama не запущен или не отвечает).\n"
            f"Техническая причина: {exc}"
        )
