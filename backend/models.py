from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Table, Text, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


recommended_element_competencies = Table(
    "recommended_element_competencies",
    Base.metadata,
    Column("recommended_element_id", ForeignKey("recommended_elements.id"), primary_key=True),
    Column("competency_id", ForeignKey("competencies.id"), primary_key=True),
)


class Competency(Base):
    __tablename__ = "competencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    recommended_elements: Mapped[list["RecommendedElement"]] = relationship(
        secondary=recommended_element_competencies,
        back_populates="competencies",
    )


class RecommendedElement(Base):
    __tablename__ = "recommended_elements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    program_code: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    element_type: Mapped[str] = mapped_column(String(20), nullable=False)
    part: Mapped[str] = mapped_column(String(20), nullable=False)
    credits: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    semesters: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    practice_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_fgos_mandatory: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fgos_requirement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    competencies: Mapped[list["Competency"]] = relationship(
        secondary=recommended_element_competencies,
        back_populates="recommended_elements",
    )


class CurriculumPlan(Base):
    __tablename__ = "curriculum_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    program_code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    elements: Mapped[list["PlanElement"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["CheckReport"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class PlanElement(Base):
    __tablename__ = "plan_elements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("curriculum_plans.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    block: Mapped[str] = mapped_column(String(20), nullable=False)
    part: Mapped[str] = mapped_column(String(20), nullable=False)
    credits: Mapped[float] = mapped_column(Float, nullable=False)
    hours: Mapped[float] = mapped_column(Float, nullable=False)
    extra_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    semesters: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    competency_ids: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    practice_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fgos_requirement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_element_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommended_elements.id"),
        nullable=True,
    )

    plan: Mapped["CurriculumPlan"] = relationship(back_populates="elements")

    @property
    def total_hours(self) -> float:
        return float(self.hours or 0) + float(self.extra_hours or 0)


class NormativeParam(Base):
    __tablename__ = "normative_params"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)


class CheckReport(Base):
    __tablename__ = "check_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("curriculum_plans.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    results: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    llm_recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped["CurriculumPlan"] = relationship(back_populates="reports")
