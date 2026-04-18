from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import CheckReport, Competency, CurriculumPlan, PlanElement
from backend.modules.plan_builder.calculator import (
    aggregate_by_block,
    aggregate_by_semester,
    aggregate_by_year,
    aggregate_mandatory_percent,
)
from backend.modules.validation.engine import run_checks
from backend.schemas import (
    CurriculumPlanCreate,
    CurriculumPlanListResponse,
    CurriculumPlanRead,
    CurriculumPlanResponse,
    CurriculumPlanStatusUpdate,
    PlanDeletionPayload,
    PlanDeletionResponse,
    PlanElementCreate,
    PlanElementRead,
    PlanElementResponse,
    PlanElementUpdate,
    Table2Data,
    Table2Response,
)


router = APIRouter(prefix="/api/v1/plans", tags=["table2"])

ALLOWED_PLAN_STATUSES = {"draft", "checked", "approved"}


def _normalize_semesters(semesters: list[int] | None) -> list[int]:
    if not semesters:
        return []
    return sorted({int(value) for value in semesters if int(value) > 0})


def _semester_sort_key(element: PlanElement) -> tuple[int, ...]:
    semesters = _normalize_semesters(element.semesters)
    if not semesters:
        return (999,)
    return tuple(semesters)


def _get_plan_or_404(plan_id: int, db: Session) -> CurriculumPlan:
    plan = db.query(CurriculumPlan).filter(CurriculumPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan with id={plan_id} was not found")
    return plan


def _get_plan_element_or_404(plan_id: int, element_id: int, db: Session) -> PlanElement:
    element = (
        db.query(PlanElement)
        .filter(PlanElement.plan_id == plan_id, PlanElement.id == element_id)
        .first()
    )
    if element is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plan element with id={element_id} for plan id={plan_id} was not found",
        )
    return element


def _build_grouped_elements(elements: list[PlanElement]) -> dict[str, dict[str, list[PlanElementRead]]]:
    grouped: dict[str, dict[str, list[PlanElementRead]]] = {}
    for element in sorted(elements, key=lambda item: (item.block, item.part, _semester_sort_key(item), item.id)):
        block = str(element.block)
        part = str(element.part)
        grouped.setdefault(block, {}).setdefault(part, []).append(PlanElementRead.model_validate(element))
    return grouped


def _build_aggregates(elements: list[PlanElement]) -> dict[str, object]:
    countable_elements = [element for element in elements if str(element.block) != "fac"]
    total_credits = sum(element.credits for element in countable_elements)
    total_hours = sum(element.hours + float(element.extra_hours or 0) for element in elements)
    total_base_hours = sum(element.hours for element in elements)
    total_extra_hours = sum(float(element.extra_hours or 0) for element in elements)
    return {
        "total_credits": total_credits,
        "total_hours": total_hours,
        "total_base_hours": total_base_hours,
        "total_extra_hours": total_extra_hours,
        "by_block": aggregate_by_block(countable_elements),
        "by_year": aggregate_by_year(countable_elements),
        "by_semester": aggregate_by_semester(countable_elements),
        "mandatory_percent": aggregate_mandatory_percent(countable_elements),
    }


def _normalize_competency_ids(competency_ids: list[int], db: Session) -> list[int]:
    if not competency_ids:
        return []

    valid_ids = {row[0] for row in db.query(Competency.id).filter(Competency.id.in_(competency_ids)).all()}
    return [competency_id for competency_id in competency_ids if competency_id in valid_ids]


def _sanitize_element_payload(payload_data: dict[str, object], db: Session) -> dict[str, object]:
    competency_ids = payload_data.get("competency_ids", [])
    semesters = payload_data.get("semesters", [])
    payload_data["competency_ids"] = _normalize_competency_ids(list(competency_ids or []), db)
    payload_data["semesters"] = _normalize_semesters(list(semesters or []))
    if "extra_hours" in payload_data:
        payload_data["extra_hours"] = float(payload_data.get("extra_hours") or 0)
    return payload_data


def _sanitize_element_competency_ids(element: PlanElement, db: Session) -> bool:
    normalized_ids = _normalize_competency_ids(element.competency_ids, db)
    normalized_semesters = _normalize_semesters(element.semesters)

    if normalized_ids == element.competency_ids and normalized_semesters == element.semesters:
        return False

    element.competency_ids = normalized_ids
    element.semesters = normalized_semesters
    element.extra_hours = float(element.extra_hours or 0)
    db.add(element)
    return True


def _get_latest_report(plan_id: int, db: Session) -> CheckReport | None:
    return (
        db.query(CheckReport)
        .filter(CheckReport.plan_id == plan_id)
        .order_by(CheckReport.created_at.desc(), CheckReport.id.desc())
        .first()
    )


def _assert_can_approve(plan_id: int, db: Session) -> None:
    report = _get_latest_report(plan_id, db)
    if report is None:
        report = run_checks(plan_id, db)

    blocking_levels = {"critical", "error"}
    blocking = [item for item in report.results if item["level"] in blocking_levels]
    if blocking:
        raise HTTPException(
            status_code=400,
            detail="Plan cannot be approved while critical errors or errors are present",
        )


@router.post("", response_model=CurriculumPlanResponse)
def create_plan(payload: CurriculumPlanCreate, db: Session = Depends(get_db)) -> CurriculumPlanResponse:
    plan = CurriculumPlan(name=payload.name, status="draft")
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return CurriculumPlanResponse(data=CurriculumPlanRead.model_validate(plan))


@router.get("", response_model=CurriculumPlanListResponse)
def list_plans(db: Session = Depends(get_db)) -> CurriculumPlanListResponse:
    plans = db.query(CurriculumPlan).order_by(CurriculumPlan.updated_at.desc(), CurriculumPlan.id.desc()).all()
    return CurriculumPlanListResponse(data=[CurriculumPlanRead.model_validate(plan) for plan in plans])


@router.delete("/{plan_id}", response_model=PlanDeletionResponse)
def delete_plan(plan_id: int, db: Session = Depends(get_db)) -> PlanDeletionResponse:
    plan = _get_plan_or_404(plan_id, db)
    db.delete(plan)
    db.commit()
    return PlanDeletionResponse(data=PlanDeletionPayload(deleted=True, plan_id=plan_id))


@router.get("/{plan_id}/table2", response_model=Table2Response)
def get_table2(plan_id: int, db: Session = Depends(get_db)) -> Table2Response:
    plan = _get_plan_or_404(plan_id, db)
    elements = db.query(PlanElement).filter(PlanElement.plan_id == plan_id).all()

    dirty = False
    for element in elements:
        dirty = _sanitize_element_competency_ids(element, db) or dirty
    if dirty:
        db.commit()
        for element in elements:
            db.refresh(element)

    return Table2Response(
        data=Table2Data(
            plan=CurriculumPlanRead.model_validate(plan),
            grouped_elements=_build_grouped_elements(elements),
            aggregates=_build_aggregates(elements),
        )
    )


@router.post("/{plan_id}/table2/elements", response_model=PlanElementResponse)
def create_plan_element(
    plan_id: int,
    payload: PlanElementCreate,
    db: Session = Depends(get_db),
) -> PlanElementResponse:
    _get_plan_or_404(plan_id, db)
    payload_data = _sanitize_element_payload(payload.model_dump(), db)
    element = PlanElement(plan_id=plan_id, hours=0, **payload_data)
    db.add(element)
    db.commit()
    db.refresh(element)
    return PlanElementResponse(data=PlanElementRead.model_validate(element))


@router.patch("/{plan_id}/table2/elements/{element_id}", response_model=PlanElementResponse)
def update_plan_element(
    plan_id: int,
    element_id: int,
    payload: PlanElementUpdate,
    db: Session = Depends(get_db),
) -> PlanElementResponse:
    element = _get_plan_element_or_404(plan_id, element_id, db)
    for field, value in _sanitize_element_payload(payload.model_dump(exclude_unset=True), db).items():
        setattr(element, field, value)
    db.add(element)
    db.commit()
    db.refresh(element)
    return PlanElementResponse(data=PlanElementRead.model_validate(element))


@router.delete("/{plan_id}/table2/elements/{element_id}")
def delete_plan_element(plan_id: int, element_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    element = _get_plan_element_or_404(plan_id, element_id, db)
    db.delete(element)
    db.commit()
    return {"data": {"deleted": True, "element_id": element_id}}


@router.patch("/{plan_id}/status", response_model=CurriculumPlanResponse)
def update_plan_status(
    plan_id: int,
    payload: CurriculumPlanStatusUpdate,
    db: Session = Depends(get_db),
) -> CurriculumPlanResponse:
    plan = _get_plan_or_404(plan_id, db)
    if payload.status not in ALLOWED_PLAN_STATUSES:
        raise HTTPException(status_code=400, detail=f"Unsupported plan status '{payload.status}'")

    if payload.status == "approved":
        _assert_can_approve(plan_id, db)

    plan.status = payload.status
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return CurriculumPlanResponse(data=CurriculumPlanRead.model_validate(plan))
