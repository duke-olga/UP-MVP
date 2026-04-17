import json
from pathlib import Path

from sqlalchemy.orm import Session, selectinload

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
    return {code for code, competency in competency_map.items() if competency.type in auto_types}


def _recommended_element_key(item: dict) -> tuple:
    return (
        item["name"],
        item["element_type"],
        item["part"],
        item.get("credits"),
        item.get("semester"),
        item["source"],
    )


def _sync_competencies(db: Session, payload: list[dict]) -> dict[str, models.Competency]:
    existing_by_code = {item.code: item for item in db.query(models.Competency).all()}
    payload_codes = {item["code"] for item in payload}

    for stale_code, stale_competency in list(existing_by_code.items()):
        if stale_code in payload_codes:
            continue
        stale_competency.recommended_elements.clear()
        db.flush()
        db.delete(stale_competency)
        existing_by_code.pop(stale_code, None)

    for item in payload:
        competency = existing_by_code.get(item["code"])
        if competency is None:
            competency = models.Competency(
                code=item["code"],
                type=item["type"],
                name=item["name"],
                description=item["description"],
            )
            db.add(competency)
            db.flush()
            existing_by_code[competency.code] = competency
            continue

        competency.type = item["type"]
        competency.name = item["name"]
        competency.description = item["description"]
        db.add(competency)

    db.flush()
    return existing_by_code


def _sync_recommended_elements(
    db: Session,
    payload: list[dict],
    competency_map: dict[str, models.Competency],
) -> None:
    existing_elements = (
        db.query(models.RecommendedElement)
        .options(selectinload(models.RecommendedElement.competencies))
        .all()
    )
    existing_by_key = {
        _recommended_element_key(
            {
                "name": item.name,
                "element_type": item.element_type,
                "part": item.part,
                "credits": item.credits,
                "semester": item.semester,
                "source": item.source,
            }
        ): item
        for item in existing_elements
    }

    auto_competency_codes = _get_auto_competency_codes(competency_map)
    payload_by_key = {_recommended_element_key(item): item for item in payload}

    for key, element in list(existing_by_key.items()):
        seed_item = payload_by_key.get(key)
        if seed_item is None:
            element.competencies.clear()
            db.flush()
            db.delete(element)
            existing_by_key.pop(key, None)
            continue

        filtered_codes = [code for code in seed_item["competency_codes"] if code in auto_competency_codes]
        if not filtered_codes:
            element.competencies.clear()
            db.flush()
            db.delete(element)
            existing_by_key.pop(key, None)
            continue

        element.name = seed_item["name"]
        element.element_type = seed_item["element_type"]
        element.part = seed_item["part"]
        element.credits = seed_item.get("credits")
        element.semester = seed_item.get("semester")
        element.source = seed_item["source"]
        element.competencies = [competency_map[code] for code in filtered_codes]
        db.add(element)

    for key, seed_item in payload_by_key.items():
        if key in existing_by_key:
            continue

        filtered_codes = [code for code in seed_item["competency_codes"] if code in auto_competency_codes]
        if not filtered_codes:
            continue

        recommended_element = models.RecommendedElement(
            name=seed_item["name"],
            element_type=seed_item["element_type"],
            part=seed_item["part"],
            credits=seed_item.get("credits"),
            semester=seed_item.get("semester"),
            source=seed_item["source"],
        )
        recommended_element.competencies = [competency_map[code] for code in filtered_codes]
        db.add(recommended_element)


def _sync_normative_params(db: Session, payload: list[dict]) -> None:
    existing_by_key = {item.key: item for item in db.query(models.NormativeParam).all()}
    payload_keys = {item["key"] for item in payload}

    for stale_key, stale_param in list(existing_by_key.items()):
        if stale_key not in payload_keys:
            db.delete(stale_param)
            existing_by_key.pop(stale_key, None)

    for item in payload:
        param = existing_by_key.get(item["key"])
        if param is None:
            db.add(models.NormativeParam(key=item["key"], value=item["value"]))
            continue
        param.value = item["value"]
        db.add(param)


def load_seed_data(db: Session) -> None:
    competencies_payload = _read_json("competencies.json")
    recommended_elements_payload = _group_recommended_elements(_read_json("poop_disciplines.json"))
    normative_params_payload = _read_json("normative_params.json")

    competency_map = _sync_competencies(db, competencies_payload)
    _sync_recommended_elements(db, recommended_elements_payload, competency_map)
    _sync_normative_params(db, normative_params_payload)

    db.commit()
