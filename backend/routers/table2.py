from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import CheckReport, CurriculumPlan, PlanElement
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
    PlanElementCreate,
    PlanElementRead,
    PlanElementResponse,
    PlanElementUpdate,
    Table2Data,
    Table2Response,
)


router = APIRouter(prefix="/api/v1/plans", tags=["table2"])

ALLOWED_PLAN_STATUSES = {"draft", "checked", "approved"}


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
    for element in elements:
        block = str(element.block)
        part = str(element.part)
        grouped.setdefault(block, {}).setdefault(part, []).append(PlanElementRead.model_validate(element))
    return grouped


def _build_aggregates(elements: list[PlanElement]) -> dict[str, object]:
    total_credits = sum(element.credits for element in elements)
    total_hours = sum(element.hours for element in elements)
    return {
        "total_credits": total_credits,
        "total_hours": total_hours,
        "by_block": aggregate_by_block(elements),
        "by_year": aggregate_by_year(elements),
        "by_semester": aggregate_by_semester(elements),
        "mandatory_percent": aggregate_mandatory_percent(elements),
    }


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
    return CurriculumPlanListResponse(
        data=[CurriculumPlanRead.model_validate(plan) for plan in plans]
    )


@router.get("/{plan_id}/table2", response_model=Table2Response)
def get_table2(plan_id: int, db: Session = Depends(get_db)) -> Table2Response:
    plan = _get_plan_or_404(plan_id, db)
    elements = (
        db.query(PlanElement)
        .filter(PlanElement.plan_id == plan_id)
        .order_by(PlanElement.block, PlanElement.part, PlanElement.semester, PlanElement.id)
        .all()
    )
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
    element = PlanElement(plan_id=plan_id, hours=0, **payload.model_dump())
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
    for field, value in payload.model_dump(exclude_unset=True).items():
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
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported plan status '{payload.status}'",
        )

    if payload.status == "approved":
        _assert_can_approve(plan_id, db)

    plan.status = payload.status
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return CurriculumPlanResponse(data=CurriculumPlanRead.model_validate(plan))
