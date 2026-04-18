from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import CheckReport, CurriculumPlan, NormativeParam, PlanElement
from backend.modules.plan_builder.calculator import (
    aggregate_by_block,
    aggregate_by_semester,
    aggregate_by_year,
    aggregate_mandatory_percent,
)
from backend.schemas import CheckReportRead, CurriculumPlanRead, Table3Data, Table3Response, ValidationSummary


router = APIRouter(prefix="/api/v1/plans", tags=["table3"])


def _get_plan_or_404(plan_id: int, db: Session) -> CurriculumPlan:
    plan = db.query(CurriculumPlan).filter(CurriculumPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan with id={plan_id} was not found")
    return plan


def _get_normative_params(db: Session) -> dict[str, float]:
    params = db.query(NormativeParam).all()
    return {item.key: item.value for item in params}


def _get_latest_report(plan_id: int, db: Session) -> CheckReport | None:
    return (
        db.query(CheckReport)
        .filter(CheckReport.plan_id == plan_id)
        .order_by(CheckReport.created_at.desc(), CheckReport.id.desc())
        .first()
    )


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


def _build_deviations(aggregates: dict[str, object], params: dict[str, float]) -> dict[str, object]:
    by_block = aggregates["by_block"]
    by_year = aggregates["by_year"]
    mandatory_percent = aggregates["mandatory_percent"]
    total_credits = aggregates["total_credits"]

    return {
        "total_credits": {
            "actual": total_credits,
            "expected": params["X_total"],
            "delta": total_credits - params["X_total"],
        },
        "by_block": {
            "1": {
                "actual": by_block.get("1", 0.0),
                "expected": params["X_b1"],
                "delta": by_block.get("1", 0.0) - params["X_b1"],
            },
            "2": {
                "actual": by_block.get("2", 0.0),
                "expected": params["X_b2"],
                "delta": by_block.get("2", 0.0) - params["X_b2"],
            },
            "3": {
                "actual": by_block.get("3", 0.0),
                "expected": params["X_b3"],
                "delta": by_block.get("3", 0.0) - params["X_b3"],
            },
        },
        "by_year": {
            str(year): {
                "actual": credits,
                "expected": params["X_year"],
                "delta": credits - params["X_year"],
            }
            for year, credits in by_year.items()
        },
        "mandatory_percent": {
            "actual": mandatory_percent,
            "expected": params["X_mandatory_percent"],
            "delta": mandatory_percent - params["X_mandatory_percent"],
        },
    }


def _build_validation_summary(report: CheckReport | None) -> ValidationSummary:
    if report is None or not report.results:
        return ValidationSummary(
            status="ok",
            has_blocking_issues=False,
            has_warnings=False,
            critical_count=0,
            error_count=0,
            warning_count=0,
        )

    critical_count = sum(1 for item in report.results if item["level"] == "critical")
    error_count = sum(1 for item in report.results if item["level"] == "error")
    warning_count = sum(1 for item in report.results if item["level"] == "warning")
    has_blocking_issues = critical_count > 0 or error_count > 0

    if critical_count > 0:
        status = "critical"
    elif error_count > 0:
        status = "error"
    elif warning_count > 0:
        status = "warning"
    else:
        status = "ok"

    return ValidationSummary(
        status=status,
        has_blocking_issues=has_blocking_issues,
        has_warnings=warning_count > 0,
        critical_count=critical_count,
        error_count=error_count,
        warning_count=warning_count,
    )


@router.get("/{plan_id}/table3", response_model=Table3Response)
def get_table3(plan_id: int, db: Session = Depends(get_db)) -> Table3Response:
    plan = _get_plan_or_404(plan_id, db)
    elements = (
        db.query(PlanElement)
        .filter(PlanElement.plan_id == plan_id)
        .order_by(PlanElement.block, PlanElement.part, PlanElement.semester, PlanElement.id)
        .all()
    )
    params = _get_normative_params(db)
    aggregates = _build_aggregates(elements)
    deviations = _build_deviations(aggregates, params)
    latest_report = _get_latest_report(plan_id, db)

    return Table3Response(
        data=Table3Data(
            plan=CurriculumPlanRead.model_validate(plan),
            aggregates=aggregates,
            deviations=deviations,
            validation_summary=_build_validation_summary(latest_report),
            latest_report=CheckReportRead.model_validate(latest_report) if latest_report else None,
        )
    )
