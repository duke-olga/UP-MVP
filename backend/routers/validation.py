from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.modules.llm_explainer.service import generate_recommendations
from backend.modules.validation.engine import run_checks
from backend.schemas import CheckReportRead


router = APIRouter(prefix="/api/v1/plans", tags=["validation"])


@router.post("/{plan_id}/validate", response_model=CheckReportRead)
def validate_plan(plan_id: int, db: Session = Depends(get_db)) -> CheckReportRead:
    try:
        report = run_checks(plan_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    report.llm_recommendations = generate_recommendations(report)
    db.add(report)
    db.commit()
    db.refresh(report)
    return CheckReportRead.model_validate(report)
