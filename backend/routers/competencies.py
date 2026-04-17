from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Competency
from backend.schemas import CompetencyGroupedResponse, CompetencyRead


router = APIRouter(prefix="/api/v1/competencies", tags=["competencies"])


@router.get("", response_model=CompetencyGroupedResponse)
def list_competencies(db: Session = Depends(get_db)) -> CompetencyGroupedResponse:
    competencies = db.query(Competency).order_by(Competency.type, Competency.code).all()
    grouped: dict[str, list[CompetencyRead]] = {}

    for competency in competencies:
        grouped.setdefault(competency.type, []).append(CompetencyRead.model_validate(competency))

    return CompetencyGroupedResponse(data=grouped)
