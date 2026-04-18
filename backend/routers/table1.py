from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from backend.database import get_db
from backend.models import Competency, CurriculumPlan, PlanElement, RecommendedElement
from backend.schemas import (
    CompetencyRead,
    Table1CompetencySection,
    Table1RecommendedElement,
    Table1Response,
    Table1TransferRequest,
    Table1TransferResponse,
)


router = APIRouter(prefix="/api/v1/plans", tags=["table1"])

MANUAL_MODE_TYPE = "ПКС"
AUTO_MODE_TYPES = {"УК", "ОПК", "ПК"}
SOURCE_LABELS = {
    "poop": "ПООП",
    "best_practice": "Лучшие практики",
    "local_requirement": "Локальные требования вуза",
    "local": "Локальные требования вуза",
}


def _get_plan_or_404(plan_id: int, db: Session) -> CurriculumPlan:
    plan = db.query(CurriculumPlan).filter(CurriculumPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan with id={plan_id} was not found")
    return plan


def _get_source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, "Источник не указан")


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
        semester=element.semester,
        source=element.source,
        source_label=_get_source_label(element.source),
        competency_codes=[competency.code for competency in sorted(element.competencies, key=lambda item: item.code)],
        selected=element.id in selected_source_ids,
    )


def _classify_recommendations(
    competency: Competency,
    selected_source_ids: set[int],
) -> tuple[list[Table1RecommendedElement], list[Table1RecommendedElement], list[Table1RecommendedElement]]:
    mandatory_disciplines: list[Table1RecommendedElement] = []
    variative_disciplines: list[Table1RecommendedElement] = []
    mandatory_practices: list[Table1RecommendedElement] = []

    for element in sorted(competency.recommended_elements, key=lambda item: (item.part, item.name, item.id)):
        payload = _build_recommendation_payload(element, selected_source_ids)
        if element.element_type == "discipline" and element.part == "mandatory":
            mandatory_disciplines.append(payload)
        elif element.element_type == "discipline" and element.part == "variative":
            variative_disciplines.append(payload)
        elif element.element_type == "practice" and element.part == "mandatory":
            mandatory_practices.append(payload)

    return mandatory_disciplines, variative_disciplines, mandatory_practices


def _get_selected_source_ids(plan_id: int, db: Session) -> set[int]:
    rows = (
        db.query(PlanElement.source_element_id)
        .filter(PlanElement.plan_id == plan_id, PlanElement.source_element_id.isnot(None))
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def _get_block_for_recommendation(element: RecommendedElement) -> str:
    return "1" if element.element_type == "discipline" else "2"


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
    if existing is not None:
        existing.name = element.name
        existing.block = _get_block_for_recommendation(element)
        existing.part = element.part
        existing.credits = float(element.credits or 0.0)
        existing.semester = element.semester
        existing.competency_ids = competency_ids
        db.add(existing)
        return existing, False

    created = PlanElement(
        plan_id=plan_id,
        name=element.name,
        block=_get_block_for_recommendation(element),
        part=element.part,
        credits=float(element.credits or 0.0),
        hours=0,
        semester=element.semester,
        competency_ids=competency_ids,
        source_element_id=element.id,
    )
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
    selected_source_ids = _get_selected_source_ids(plan_id, db)

    sections: list[Table1CompetencySection] = []
    for competency in competencies:
        if competency.type == MANUAL_MODE_TYPE:
            sections.append(
                Table1CompetencySection(
                    competency=CompetencyRead.model_validate(competency),
                    mode="manual_only",
                    mandatory_disciplines=[],
                    variative_disciplines=[],
                    mandatory_practices=[],
                )
            )
            continue

        mandatory_disciplines, variative_disciplines, mandatory_practices = _classify_recommendations(
            competency,
            selected_source_ids,
        )
        sections.append(
            Table1CompetencySection(
                competency=CompetencyRead.model_validate(competency),
                mode="recommendation" if competency.type in AUTO_MODE_TYPES else "manual_only",
                mandatory_disciplines=mandatory_disciplines,
                variative_disciplines=variative_disciplines,
                mandatory_practices=mandatory_practices,
            )
        )

    return Table1Response(data=sections)


@router.post("/{plan_id}/table1/transfer", response_model=Table1TransferResponse)
def transfer_table1_to_table2(
    plan_id: int,
    payload: Table1TransferRequest,
    db: Session = Depends(get_db),
) -> Table1TransferResponse:
    _get_plan_or_404(plan_id, db)

    selected_ids = {item.element_id for item in payload.selections if item.selected}
    recommendations = (
        db.query(RecommendedElement)
        .options(selectinload(RecommendedElement.competencies))
        .all()
    )

    transferred_ids: list[int] = []
    created_count = 0
    updated_count = 0

    for recommendation in recommendations:
        competency_types = {competency.type for competency in recommendation.competencies}
        if MANUAL_MODE_TYPE in competency_types:
            continue

        should_transfer = (
            recommendation.part == "mandatory"
            or (
                recommendation.part == "variative"
                and recommendation.element_type == "discipline"
                and recommendation.id in selected_ids
            )
        )
        if not should_transfer:
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
        }
    )
