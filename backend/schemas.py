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
    semesters: list[int] = []
    source: str
    competency_codes: list[str] = []


class RecommendedElementRead(RecommendedElementBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class Table1RecommendedElement(BaseModel):
    id: int
    name: str
    element_type: str
    part: str
    credits: float | None = None
    semesters: list[int]
    source: str
    source_label: str
    competency_codes: list[str]
    selected: bool = False


class CurriculumPlanBase(BaseModel):
    name: str
    status: str


class CurriculumPlanCreate(BaseModel):
    name: str


class CurriculumPlanStatusUpdate(BaseModel):
    status: str


class CurriculumPlanRead(CurriculumPlanBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanDeletionPayload(BaseModel):
    deleted: bool
    plan_id: int


class PlanDeletionResponse(BaseModel):
    data: PlanDeletionPayload


class PlanElementBase(BaseModel):
    name: str
    block: str
    part: str
    credits: float
    semesters: list[int] = []
    competency_ids: list[int]
    source_element_id: int | None = None


class PlanElementCreate(PlanElementBase):
    pass


class PlanElementUpdate(BaseModel):
    name: str | None = None
    block: str | None = None
    part: str | None = None
    credits: float | None = None
    semesters: list[int] | None = None
    competency_ids: list[int] | None = None
    source_element_id: int | None = None


class PlanElementRead(PlanElementBase):
    id: int
    plan_id: int
    hours: float

    model_config = ConfigDict(from_attributes=True)


class NormativeParamRead(BaseModel):
    id: int
    key: str
    value: float

    model_config = ConfigDict(from_attributes=True)


class CheckResult(BaseModel):
    rule_id: int
    level: str
    message: str
    actual: str | float | int | None = None
    expected: str | float | int | None = None


class CheckReportRead(BaseModel):
    id: int
    plan_id: int
    created_at: datetime
    results: list[CheckResult]
    llm_recommendations: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ValidationSummary(BaseModel):
    status: str
    has_blocking_issues: bool
    has_warnings: bool
    critical_count: int
    error_count: int
    warning_count: int


class CompetencyGroup(BaseModel):
    type: str
    items: list[CompetencyRead]


class CompetencyGroupedResponse(BaseModel):
    data: dict[str, list[CompetencyRead]]


class CurriculumPlanListResponse(BaseModel):
    data: list[CurriculumPlanRead]


class CurriculumPlanResponse(BaseModel):
    data: CurriculumPlanRead


class PlanElementResponse(BaseModel):
    data: PlanElementRead


class Table2Data(BaseModel):
    plan: CurriculumPlanRead
    grouped_elements: dict[str, dict[str, list[PlanElementRead]]]
    aggregates: dict[str, object]


class Table2Response(BaseModel):
    data: Table2Data


class Table1CompetencySection(BaseModel):
    competency: CompetencyRead
    mode: str
    mandatory_disciplines: list[Table1RecommendedElement]
    variative_disciplines: list[Table1RecommendedElement]
    mandatory_practices: list[Table1RecommendedElement]


class Table1Response(BaseModel):
    data: list[Table1CompetencySection]


class Table1TransferItem(BaseModel):
    element_id: int
    selected: bool


class Table1TransferRequest(BaseModel):
    selections: list[Table1TransferItem]


class Table1TransferResponse(BaseModel):
    data: dict[str, object]


class Table3Data(BaseModel):
    plan: CurriculumPlanRead
    aggregates: dict[str, object]
    deviations: dict[str, object]
    validation_summary: ValidationSummary
    latest_report: CheckReportRead | None = None


class Table3Response(BaseModel):
    data: Table3Data
