from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from backend.database import get_db
from backend.models import Competency, CurriculumPlan, PlanElement, RecommendedElement
from backend.schemas import (
    CompetencyRead,
    Table1CompetencySection,
    Table1Data,
    Table1FgosGroup,
    Table1RecommendedElement,
    Table1Response,
    Table1SelectionSummary,
    Table1TransferRequest,
    Table1TransferResponse,
)


router = APIRouter(prefix="/api/v1/plans", tags=["table1"])

MANUAL_MODE_TYPE = "ПКС"
AUTO_MODE_TYPES = {"УК", "ОПК", "ПК"}
SOURCE_LABELS = {
    "poop": "ПООП",
    "best_practices": "Лучшие практики",
    "best_practice": "Лучшие практики",
    "local_requirement": "Локальные требования вуза",
    "local": "Локальные требования вуза",
}
FGOS_DISCIPLINE_TITLES = {
    "philosophy": "Философия",
    "history": "История",
    "foreign_language": "Иностранный язык",
    "life_safety": "Безопасность жизнедеятельности",
}
FGOS_PRACTICE_TITLES = {
    "educational_practice": "Учебная практика",
    "industrial_practice": "Производственная практика",
}


def _get_plan_or_404(plan_id: int, db: Session) -> CurriculumPlan:
    plan = db.query(CurriculumPlan).filter(CurriculumPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan with id={plan_id} was not found")
    return plan


def _get_source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, "Источник не указан")


def _get_selected_source_ids(plan_id: int, db: Session) -> set[int]:
    rows = (
        db.query(PlanElement.source_element_id)
        .filter(PlanElement.plan_id == plan_id, PlanElement.source_element_id.isnot(None))
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def _build_recommendation_payload(
    element: RecommendedElement,
    selected_source_ids: set[int],
) -> Table1RecommendedElement:
    return Table1RecommendedElement(
        id=element.id,
        name=element.name,
        element_type=element.element_type,
        part=element.part,
        credits=element.credits,
        extra_hours=float(element.extra_hours or 0),
        semesters=sorted(element.semesters or []),
        source=element.source,
        source_label=_get_source_label(element.source),
        practice_type=element.practice_type,
        fgos_requirement=element.fgos_requirement,
        competency_codes=[competency.code for competency in sorted(element.competencies, key=lambda item: item.code)],
        selected=element.id in selected_source_ids,
    )


def _sort_key(item: RecommendedElement) -> tuple[int, str, int]:
    semesters = sorted(item.semesters or [])
    first_semester = semesters[0] if semesters else 999
    return (first_semester, item.name, item.id)


def _classify_competency_recommendations(
    competency: Competency,
    selected_source_ids: set[int],
) -> tuple[list[Table1RecommendedElement], list[Table1RecommendedElement], list[Table1RecommendedElement]]:
    mandatory_disciplines: list[Table1RecommendedElement] = []
    variative_disciplines: list[Table1RecommendedElement] = []
    mandatory_practices: list[Table1RecommendedElement] = []

    for element in sorted(competency.recommended_elements, key=_sort_key):
        if element.is_fgos_mandatory:
            continue

        payload = _build_recommendation_payload(element, selected_source_ids)
        if element.element_type == "discipline" and element.part == "mandatory":
            mandatory_disciplines.append(payload)
        elif element.element_type == "discipline" and element.part == "variative":
            variative_disciplines.append(payload)
        elif element.element_type == "practice" and element.part == "mandatory":
            mandatory_practices.append(payload)

    return mandatory_disciplines, variative_disciplines, mandatory_practices


def _build_fgos_groups(
    requirements: dict[str, str],
    recommendations: list[RecommendedElement],
    selected_source_ids: set[int],
    selection_mode: str,
) -> list[Table1FgosGroup]:
    grouped_items: dict[str, list[RecommendedElement]] = defaultdict(list)
    for recommendation in recommendations:
        if recommendation.fgos_requirement in requirements:
            grouped_items[str(recommendation.fgos_requirement)].append(recommendation)

    groups: list[Table1FgosGroup] = []
    for requirement, title in requirements.items():
        items = [
            _build_recommendation_payload(item, selected_source_ids)
            for item in sorted(grouped_items.get(requirement, []), key=_sort_key)
        ]
        selected_count = sum(1 for item in items if item.selected)
        groups.append(
            Table1FgosGroup(
                requirement=requirement,
                title=title,
                selection_mode=selection_mode,
                selected_count=selected_count,
                is_complete=selected_count >= 1,
                items=items,
            )
        )
    return groups


def _build_selection_summary(
    fgos_disciplines: list[Table1FgosGroup],
    fgos_practices: list[Table1FgosGroup],
) -> Table1SelectionSummary:
    missing_discipline_requirements = [item.title for item in fgos_disciplines if not item.is_complete]
    missing_practice_requirements = [item.title for item in fgos_practices if not item.is_complete]
    return Table1SelectionSummary(
        required_disciplines_complete=not missing_discipline_requirements,
        required_practices_complete=not missing_practice_requirements,
        missing_discipline_requirements=missing_discipline_requirements,
        missing_practice_requirements=missing_practice_requirements,
    )


def _get_block_for_recommendation(element: RecommendedElement) -> str:
    return "1" if element.element_type == "discipline" else "2"


def _is_auto_transferable(recommendation: RecommendedElement) -> bool:
    competency_types = {competency.type for competency in recommendation.competencies}
    return MANUAL_MODE_TYPE not in competency_types


def _validate_fgos_single_selection(
    recommendations: list[RecommendedElement],
    selected_ids: set[int],
) -> None:
    selected_by_requirement: dict[str, list[int]] = defaultdict(list)

    for recommendation in recommendations:
        if recommendation.id not in selected_ids:
            continue
        if not recommendation.is_fgos_mandatory or recommendation.element_type != "discipline":
            continue
        if not recommendation.fgos_requirement:
            continue
        selected_by_requirement[str(recommendation.fgos_requirement)].append(recommendation.id)

    invalid_requirements = [
        FGOS_DISCIPLINE_TITLES.get(requirement, requirement)
        for requirement, ids in selected_by_requirement.items()
        if len(ids) > 1
    ]
    if invalid_requirements:
        raise HTTPException(
            status_code=400,
            detail=(
                "For each FGOS mandatory discipline, only one implementation option may be selected. "
                f"Invalid groups: {', '.join(invalid_requirements)}"
            ),
        )


def _upsert_plan_element_from_recommendation(
    plan_id: int,
    element: RecommendedElement,
    db: Session,
) -> tuple[PlanElement, bool]:
    existing = (
        db.query(PlanElement)
        .filter(
            PlanElement.plan_id == plan_id,
            PlanElement.source_element_id == element.id,
        )
        .first()
    )

    competency_ids = sorted(competency.id for competency in element.competencies)
    payload = {
        "name": element.name,
        "block": _get_block_for_recommendation(element),
        "part": element.part,
        "credits": float(element.credits or 0.0),
        "extra_hours": float(element.extra_hours or 0.0),
        "semesters": sorted(element.semesters or []),
        "competency_ids": competency_ids,
        "practice_type": element.practice_type,
        "fgos_requirement": element.fgos_requirement,
        "source_element_id": element.id,
    }

    if existing is not None:
        for field, value in payload.items():
            setattr(existing, field, value)
        db.add(existing)
        return existing, False

    created = PlanElement(plan_id=plan_id, hours=0, **payload)
    db.add(created)
    return created, True


@router.get("/{plan_id}/table1", response_model=Table1Response)
def get_table1(plan_id: int, db: Session = Depends(get_db)) -> Table1Response:
    _get_plan_or_404(plan_id, db)
    competencies = (
        db.query(Competency)
        .options(selectinload(Competency.recommended_elements).selectinload(RecommendedElement.competencies))
        .order_by(Competency.type, Competency.code)
        .all()
    )
    recommendations = (
        db.query(RecommendedElement)
        .options(selectinload(RecommendedElement.competencies))
        .order_by(RecommendedElement.name, RecommendedElement.id)
        .all()
    )
    selected_source_ids = _get_selected_source_ids(plan_id, db)

    competency_sections: list[Table1CompetencySection] = []
    for competency in competencies:
        if competency.type == MANUAL_MODE_TYPE:
            competency_sections.append(
                Table1CompetencySection(
                    competency=CompetencyRead.model_validate(competency),
                    mode="manual_only",
                    mandatory_disciplines=[],
                    variative_disciplines=[],
                    mandatory_practices=[],
                )
            )
            continue

        mandatory_disciplines, variative_disciplines, mandatory_practices = _classify_competency_recommendations(
            competency,
            selected_source_ids,
        )
        competency_sections.append(
            Table1CompetencySection(
                competency=CompetencyRead.model_validate(competency),
                mode="recommendation" if competency.type in AUTO_MODE_TYPES else "manual_only",
                mandatory_disciplines=mandatory_disciplines,
                variative_disciplines=variative_disciplines,
                mandatory_practices=mandatory_practices,
            )
        )

    fgos_disciplines = _build_fgos_groups(
        FGOS_DISCIPLINE_TITLES,
        [item for item in recommendations if item.is_fgos_mandatory and item.element_type == "discipline"],
        selected_source_ids,
        "single",
    )
    fgos_practices = _build_fgos_groups(
        FGOS_PRACTICE_TITLES,
        [item for item in recommendations if item.is_fgos_mandatory and item.element_type == "practice"],
        selected_source_ids,
        "multiple",
    )

    return Table1Response(
        data=Table1Data(
            competencies=competency_sections,
            fgos_disciplines=fgos_disciplines,
            fgos_practices=fgos_practices,
            selection_summary=_build_selection_summary(fgos_disciplines, fgos_practices),
        )
    )


@router.post("/{plan_id}/table1/transfer", response_model=Table1TransferResponse)
def transfer_table1_to_table2(
    plan_id: int,
    payload: Table1TransferRequest,
    db: Session = Depends(get_db),
) -> Table1TransferResponse:
    _get_plan_or_404(plan_id, db)

    selected_ids = {item.element_id for item in payload.selections if item.selected}
    all_recommendations = (
        db.query(RecommendedElement)
        .options(selectinload(RecommendedElement.competencies))
        .all()
    )
    recommendations = [item for item in all_recommendations if _is_auto_transferable(item)]
    _validate_fgos_single_selection(recommendations, selected_ids)

    transferred_ids: list[int] = []
    created_count = 0
    updated_count = 0
    deleted_count = 0

    recommendation_ids = {recommendation.id for recommendation in recommendations}
    stale_elements = (
        db.query(PlanElement)
        .filter(
            PlanElement.plan_id == plan_id,
            PlanElement.source_element_id.isnot(None),
            PlanElement.source_element_id.in_(recommendation_ids),
            PlanElement.source_element_id.not_in(selected_ids),
        )
        .all()
    )
    for element in stale_elements:
        db.delete(element)
        deleted_count += 1

    for recommendation in recommendations:
        if recommendation.id not in selected_ids:
            continue

        element, created = _upsert_plan_element_from_recommendation(plan_id, recommendation, db)
        if created:
            created_count += 1
        else:
            updated_count += 1
        db.flush()
        transferred_ids.append(element.id)

    db.commit()

    return Table1TransferResponse(
        data={
            "transferred_element_ids": transferred_ids,
            "created_count": created_count,
            "updated_count": updated_count,
            "deleted_count": deleted_count,
        }
    )
