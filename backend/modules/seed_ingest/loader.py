import json
from pathlib import Path

from sqlalchemy.orm import Session

from backend import models


SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


def _read_json(filename: str) -> list[dict]:
    path = SEED_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def _group_recommended_elements(payload: list[dict]) -> list[dict]:
    grouped: dict[tuple, dict] = {}

    for item in payload:
        key = (
            item["name"],
            item["element_type"],
            item["part"],
            item.get("credits"),
            item.get("semester"),
            item["source"],
        )
        bucket = grouped.setdefault(
            key,
            {
                "name": item["name"],
                "element_type": item["element_type"],
                "part": item["part"],
                "credits": item.get("credits"),
                "semester": item.get("semester"),
                "source": item["source"],
                "competency_codes": [],
            },
        )

        codes = item.get("competency_codes")
        if codes is None:
            code = item.get("competency_code")
            codes = [code] if code else []

        for code in codes:
            if code not in bucket["competency_codes"]:
                bucket["competency_codes"].append(code)

    return list(grouped.values())


def _get_auto_competency_codes(competency_map: dict[str, models.Competency]) -> set[str]:
    auto_types = {"УК", "ОПК", "ПК"}
    return {
        code
        for code, competency in competency_map.items()
        if competency.type in auto_types
    }


def load_seed_data(db: Session) -> None:
    if (
        db.query(models.Competency).first() is not None
        and db.query(models.RecommendedElement).first() is not None
        and db.query(models.NormativeParam).first() is not None
    ):
        return

    competencies_payload = _read_json("competencies.json")
    competency_map: dict[str, models.Competency] = {}

    for existing in db.query(models.Competency).all():
        competency_map[existing.code] = existing

    for item in competencies_payload:
        competency = competency_map.get(item["code"])
        if competency is None:
            competency = models.Competency(
                code=item["code"],
                type=item["type"],
                name=item["name"],
                description=item["description"],
            )
            db.add(competency)
            db.flush()
            competency_map[competency.code] = competency

    auto_competency_codes = _get_auto_competency_codes(competency_map)
    recommended_elements_payload = _group_recommended_elements(_read_json("poop_disciplines.json"))
    normative_params_payload = _read_json("normative_params.json")
    for item in recommended_elements_payload:
        filtered_codes = [
            code
            for code in item["competency_codes"]
            if code in auto_competency_codes
        ]
        if not filtered_codes:
            continue

        recommended_element = models.RecommendedElement(
            name=item["name"],
            element_type=item["element_type"],
            part=item["part"],
            credits=item.get("credits"),
            semester=item.get("semester"),
            source=item["source"],
        )
        recommended_element.competencies = [competency_map[code] for code in filtered_codes]
        db.add(recommended_element)

    existing_normative_keys = {item.key for item in db.query(models.NormativeParam).all()}
    for item in normative_params_payload:
        if item["key"] not in existing_normative_keys:
            db.add(models.NormativeParam(key=item["key"], value=item["value"]))

    db.commit()
