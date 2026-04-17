from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str


class CompetencyBase(BaseModel):
    code: str
    type: str
    name: str
    description: str


class CompetencyRead(CompetencyBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class RecommendedElementBase(BaseModel):
    name: str
    element_type: str
    part: str
    credits: float | None = None
    semester: int | None = None
    source: str
    competency_codes: list[str] = []


class RecommendedElementRead(RecommendedElementBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CurriculumPlanBase(BaseModel):
    name: str
    status: str


class CurriculumPlanRead(CurriculumPlanBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanElementBase(BaseModel):
    name: str
    block: str
    part: str
    credits: float
    hours: float
    semester: int | None = None
    competency_ids: list[int]
    source_element_id: int | None = None


class PlanElementRead(PlanElementBase):
    id: int
    plan_id: int

    model_config = ConfigDict(from_attributes=True)


class NormativeParamRead(BaseModel):
    id: int
    key: str
    value: float

    model_config = ConfigDict(from_attributes=True)


class CheckReportRead(BaseModel):
    id: int
    plan_id: int
    created_at: datetime
    results: list[dict]
    llm_recommendations: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CompetencyGroup(BaseModel):
    type: str
    items: list[CompetencyRead]


class CompetencyGroupedResponse(BaseModel):
    data: dict[str, list[CompetencyRead]]
