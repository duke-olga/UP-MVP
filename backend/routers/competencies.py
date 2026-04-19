from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Competency, RecommendedElement
from backend.schemas import CompetencyGroupedResponse, CompetencyRead, ProgramListResponse, ProgramOption


router = APIRouter(tags=["competencies"])


def _normalize_program_title(program_code: str) -> str:
    if len(program_code) == 6 and program_code.isdigit():
        return f"{program_code[:2]}.{program_code[2:4]}.{program_code[4:]}"
    return program_code


def _normalize_source_title(source: str, source_name: str | None) -> str:
    if source == "poop":
        return "ПООП"
    if source in {"local", "local_requirement"}:
        return "Локальные требования вуза"
    if not source_name:
        return "Источник не указан"
    stem = source_name.rsplit(".", maxsplit=1)[0]
    if "_" in stem:
        return stem.split("_", maxsplit=1)[1]
    return stem


@router.get("/api/v1/programs", response_model=ProgramListResponse)
def list_programs(db: Session = Depends(get_db)) -> ProgramListResponse:
    recommendations = (
        db.query(RecommendedElement)
        .filter(RecommendedElement.program_code.isnot(None))
        .order_by(RecommendedElement.program_code, RecommendedElement.id)
        .all()
    )

    programs: dict[str, dict[str, object]] = {}
    for recommendation in recommendations:
        program_code = str(recommendation.program_code)
        bucket = programs.setdefault(
            program_code,
            {
                "code": program_code,
                "title": _normalize_program_title(program_code),
                "recommendation_count": 0,
                "sources": set(),
            },
        )
        bucket["recommendation_count"] = int(bucket["recommendation_count"]) + 1
        source_title = _normalize_source_title(recommendation.source, recommendation.source_name)
        if source_title:
            bucket["sources"].add(source_title)

    data = [
        ProgramOption(
            code=item["code"],
            title=item["title"],
            recommendation_count=int(item["recommendation_count"]),
            sources=sorted(item["sources"]),
        )
        for item in programs.values()
    ]
    data.sort(key=lambda item: item.code)
    return ProgramListResponse(data=data)


@router.get("/api/v1/competencies", response_model=CompetencyGroupedResponse)
def list_competencies(db: Session = Depends(get_db)) -> CompetencyGroupedResponse:
    competencies = db.query(Competency).order_by(Competency.type, Competency.code).all()
    grouped: dict[str, list[CompetencyRead]] = {}

    for competency in competencies:
        grouped.setdefault(competency.type, []).append(CompetencyRead.model_validate(competency))

    return CompetencyGroupedResponse(data=grouped)
