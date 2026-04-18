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
        raw_semesters = item.get("semesters")
        if raw_semesters is None:
            semester = item.get("semester")
            raw_semesters = [] if semester is None else [semester]
        semesters = sorted({int(value) for value in raw_semesters})

        raw_codes = item.get("competency_codes")
        if raw_codes is None:
            code = item.get("competency_code")
            raw_codes = [] if code is None else [code]
        competency_codes = sorted({str(code) for code in raw_codes if code})

        key = (
            item["name"],
            item["element_type"],
            item["part"],
            item.get("credits"),
            item.get("extra_hours", 0),
            tuple(semesters),
            item["source"],
            item.get("practice_type"),
            bool(item.get("is_fgos_mandatory", False)),
            item.get("fgos_requirement"),
        )

        bucket = grouped.setdefault(
            key,
            {
                "name": item["name"],
                "element_type": item["element_type"],
                "part": item["part"],
                "credits": item.get("credits"),
                "extra_hours": item.get("extra_hours", 0),
                "semesters": semesters,
                "source": item["source"],
                "practice_type": item.get("practice_type"),
                "is_fgos_mandatory": bool(item.get("is_fgos_mandatory", False)),
                "fgos_requirement": item.get("fgos_requirement"),
                "competency_codes": [],
            },
        )

        for code in competency_codes:
            if code not in bucket["competency_codes"]:
                bucket["competency_codes"].append(code)

    for bucket in grouped.values():
        bucket["competency_codes"].sort()

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
        item.get("extra_hours", 0),
        tuple(item.get("semesters", [])),
        item["source"],
        item.get("practice_type"),
        bool(item.get("is_fgos_mandatory", False)),
        item.get("fgos_requirement"),
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
                "extra_hours": item.extra_hours,
                "semesters": list(item.semesters or []),
                "source": item.source,
                "practice_type": item.practice_type,
                "is_fgos_mandatory": bool(item.is_fgos_mandatory),
                "fgos_requirement": item.fgos_requirement,
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
        should_keep_without_competencies = bool(seed_item.get("is_fgos_mandatory"))
        if not filtered_codes and not should_keep_without_competencies:
            element.competencies.clear()
            db.flush()
            db.delete(element)
            existing_by_key.pop(key, None)
            continue

        element.name = seed_item["name"]
        element.element_type = seed_item["element_type"]
        element.part = seed_item["part"]
        element.credits = seed_item.get("credits")
        element.extra_hours = float(seed_item.get("extra_hours", 0) or 0)
        element.semesters = list(seed_item.get("semesters", []))
        element.source = seed_item["source"]
        element.practice_type = seed_item.get("practice_type")
        element.is_fgos_mandatory = 1 if seed_item.get("is_fgos_mandatory") else 0
        element.fgos_requirement = seed_item.get("fgos_requirement")
        element.competencies = [competency_map[code] for code in filtered_codes]
        db.add(element)

    for key, seed_item in payload_by_key.items():
        if key in existing_by_key:
            continue

        filtered_codes = [code for code in seed_item["competency_codes"] if code in auto_competency_codes]
        should_keep_without_competencies = bool(seed_item.get("is_fgos_mandatory"))
        if not filtered_codes and not should_keep_without_competencies:
            continue

        recommended_element = models.RecommendedElement(
            name=seed_item["name"],
            element_type=seed_item["element_type"],
            part=seed_item["part"],
            credits=seed_item.get("credits"),
            extra_hours=float(seed_item.get("extra_hours", 0) or 0),
            semesters=list(seed_item.get("semesters", [])),
            source=seed_item["source"],
            practice_type=seed_item.get("practice_type"),
            is_fgos_mandatory=1 if seed_item.get("is_fgos_mandatory") else 0,
            fgos_requirement=seed_item.get("fgos_requirement"),
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


def _cleanup_plan_element_competency_ids(db: Session, competency_map: dict[str, models.Competency]) -> None:
    valid_ids = {competency.id for competency in competency_map.values()}

    for element in db.query(models.PlanElement).all():
        filtered_ids = [competency_id for competency_id in element.competency_ids if competency_id in valid_ids]
        if filtered_ids == element.competency_ids:
            continue
        element.competency_ids = filtered_ids
        db.add(element)


def load_seed_data(db: Session) -> None:
    competencies_payload = _read_json("competencies.json")
    recommended_elements_payload = _group_recommended_elements(_read_json("poop_disciplines.json"))
    normative_params_payload = _read_json("normative_params.json")

    competency_map = _sync_competencies(db, competencies_payload)
    _sync_recommended_elements(db, recommended_elements_payload, competency_map)
    _sync_normative_params(db, normative_params_payload)
    _cleanup_plan_element_competency_ids(db, competency_map)

    db.commit()
