from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import CurriculumPlan, PlanElement
from backend.modules.export.xlsx_builder import build_plan_workbook


router = APIRouter(prefix="/api/v1/plans", tags=["export"])


def _get_plan_or_404(plan_id: int, db: Session) -> CurriculumPlan:
    plan = db.query(CurriculumPlan).filter(CurriculumPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan with id={plan_id} was not found")
    return plan


@router.get("/{plan_id}/export/xlsx")
def export_plan_xlsx(plan_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    plan = _get_plan_or_404(plan_id, db)
    elements = (
        db.query(PlanElement)
        .filter(PlanElement.plan_id == plan_id)
        .order_by(PlanElement.block, PlanElement.part, PlanElement.semester, PlanElement.id)
        .all()
    )

    workbook_bytes = build_plan_workbook(plan, elements)
    filename = f"plan_{plan_id}.xlsx"

    return StreamingResponse(
        BytesIO(workbook_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
