import shutil
import json
from pathlib import Path

import fitz
import backend.modules.seed_ingest.poop_pdf_importer as importer

from backend.modules.seed_ingest.poop_pdf_importer import (
    _is_aggregate_plan_name,
    extract_records_from_pdf,
    import_seed_sources,
    import_poops_from_directory,
)


def _create_minimal_pdf(path: Path, text: str) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_is_aggregate_plan_name_filters_choice_buckets() -> None:
    assert _is_aggregate_plan_name("Дисциплины по выбору")
    assert _is_aggregate_plan_name("Элективные дисциплины")
    assert not _is_aggregate_plan_name("Математический анализ")


def test_extract_records_from_real_pdf_returns_normalized_entries() -> None:
    pdf_path = Path("backend/seed/poop_pdf/090301_POOP_B.pdf")

    records = extract_records_from_pdf(pdf_path)

    assert records
    assert all(record.direction_code == "090301" for record in records)
    assert all(record.source_name == pdf_path.name for record in records)
    assert all(record.source_type == "poop" for record in records)
    assert all(record.element_type in {"discipline", "practice"} for record in records)
    assert all(record.part in {"mandatory", "variative"} for record in records)

    foreign_language = next(record for record in records if record.name == "Иностранный язык")
    assert foreign_language.credits == 12.0
    assert foreign_language.semesters == [1, 2, 3, 4, 5, 6]
    assert foreign_language.competency_codes == ["УК-4"]
    assert foreign_language.fgos_mandatory == "foreign_language"
    assert foreign_language.practice_type is None

    technological_practice = next(
        record for record in records if record.name == "технологическая (проектно-технологическая) практика"
    )
    assert technological_practice.element_type == "practice"
    assert technological_practice.part == "mandatory"
    assert technological_practice.practice_type == "educational"
    assert technological_practice.semesters == [3]

    assert not any("формируются образовательной организацией" in record.name for record in records)


def test_extract_records_from_text_layer_pdf_returns_entries() -> None:
    pdf_path = Path("backend/seed/poop_pdf/090301_POOP_B_1.pdf")
    if not pdf_path.exists():
        return

    records = extract_records_from_pdf(pdf_path)

    assert len(records) >= 20
    assert all(record.source_name == pdf_path.name for record in records)
    assert any(record.credits == 12.0 and record.fgos_mandatory == "foreign_language" for record in records)
    assert any(record.element_type == "practice" for record in records)
    assert all(not record.semesters or max(record.semesters) <= 8 for record in records)


def test_import_poops_from_directory_keeps_empty_result_without_relevant_plan_text(monkeypatch) -> None:
    monkeypatch.setattr(importer, "_extract_table_blocks_with_docling", lambda _pdf_path: ([], ["docling_skipped_in_test"]))
    workspace = Path("tests/.tmp/poop_llm_fallback")
    if workspace.exists():
        shutil.rmtree(workspace)
    input_dir = workspace / "poop_pdf"
    input_dir.mkdir(parents=True)
    _create_minimal_pdf(input_dir / "000000_empty_plan.pdf", "Примерная основная образовательная программа без учебного плана")
    output_path = workspace / "poop_disciplines.json"
    manifest_path = workspace / "poop_import_manifest.json"

    try:
        records = import_poops_from_directory(
            input_dir=input_dir,
            output_path=output_path,
            strategy="deterministic",
            manifest_path=manifest_path,
        )

        assert records == []

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload == []
    finally:
        if workspace.exists():
            shutil.rmtree(workspace)


def test_import_poops_from_directory_writes_review_dump_for_problem_file(monkeypatch) -> None:
    monkeypatch.setattr(importer, "_extract_table_blocks_with_docling", lambda _pdf_path: ([], ["docling_skipped_in_test"]))
    workspace = Path("tests/.tmp/poop_review_dump")
    if workspace.exists():
        shutil.rmtree(workspace)
    input_dir = workspace / "poop_pdf"
    review_dir = workspace / "review"
    input_dir.mkdir(parents=True)
    _create_minimal_pdf(input_dir / "000000_empty.review.pdf", "Документ без раздела 5.3 и без учебного плана")
    output_path = workspace / "poop_disciplines.json"
    manifest_path = workspace / "poop_import_manifest.json"

    try:
        records = import_poops_from_directory(
            input_dir=input_dir,
            output_path=output_path,
            strategy="deterministic",
            manifest_path=manifest_path,
            review_dir=review_dir,
        )

        assert records == []
        dump_path = review_dir / "000000_empty.review.review.json"
        assert dump_path.exists()
        payload = json.loads(dump_path.read_text(encoding="utf-8"))
        assert payload["source_name"] == "000000_empty.review.pdf"
        assert payload["needs_review"] is True
        assert "warnings" in payload
    finally:
        if workspace.exists():
            shutil.rmtree(workspace)
def test_import_seed_sources_writes_manifest() -> None:
    workspace = Path("tests/.tmp/seed_manifest")
    if workspace.exists():
        shutil.rmtree(workspace)

    poop_dir = workspace / "poop_pdf"
    poop_dir.mkdir(parents=True)
    (poop_dir / "090301_POOP_B.pdf").write_bytes(Path("backend/seed/poop_pdf/090301_POOP_B.pdf").read_bytes())
    output_path = workspace / "poop_disciplines.json"
    report_path = workspace / "poop_import_report.json"
    manifest_path = workspace / "poop_import_manifest.json"

    try:
        import_seed_sources(
            output_path=output_path,
            strategy="deterministic",
            source_types=("poop",),
            source_dirs={"poop": poop_dir},
            report_path=report_path,
            manifest_path=manifest_path,
        )

        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert len(payload) == 1
        assert payload[0]["source_name"] == "090301_POOP_B.pdf"
        assert payload[0]["sha256"]
        assert payload[0]["file_size_bytes"] > 0
    finally:
        if workspace.exists():
            shutil.rmtree(workspace)


def test_import_seed_sources_combines_poop_and_best_practices() -> None:
    workspace = Path("tests/.tmp/seed_sources")
    if workspace.exists():
        shutil.rmtree(workspace)

    poop_dir = workspace / "poop_pdf"
    best_practices_dir = workspace / "best_practices"
    poop_dir.mkdir(parents=True)
    best_practices_dir.mkdir(parents=True)

    (poop_dir / "090301_POOP_B.pdf").write_bytes(Path("backend/seed/poop_pdf/090301_POOP_B.pdf").read_bytes())
    source_best_pdf = next(Path("backend/seed/best_practices_pdf").glob("*.pdf"))
    (best_practices_dir / source_best_pdf.name).write_bytes(source_best_pdf.read_bytes())
    output_path = workspace / "poop_disciplines.json"
    report_path = workspace / "poop_import_report.json"
    manifest_path = workspace / "poop_import_manifest.json"
    review_dir = workspace / "review"

    try:
        records = import_seed_sources(
            output_path=output_path,
            strategy="deterministic",
            source_dirs={
                "poop": poop_dir,
                "best_practices": best_practices_dir,
            },
            report_path=report_path,
            manifest_path=manifest_path,
            review_dir=review_dir,
        )

        assert any(record.source_type == "poop" for record in records)
        assert any(record.source_type == "best_practices" for record in records)

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert any(item["source_type"] == "best_practices" for item in payload)
    finally:
        if workspace.exists():
            shutil.rmtree(workspace)


def test_extract_records_from_best_practices_pdf_returns_entries() -> None:
    candidates = sorted(Path("backend/seed/best_practices_pdf").glob("090304_*.pdf"))
    pdf_path = candidates[0] if candidates else next(Path("backend/seed/best_practices_pdf").glob("*.pdf"))

    records = extract_records_from_pdf(pdf_path, source_type="best_practices")

    assert records
    assert all(record.source_type == "best_practices" for record in records)
    assert any(record.name == "DevOps" for record in records)
