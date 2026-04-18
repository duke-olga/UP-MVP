import shutil
import json
from pathlib import Path

from backend.modules.seed_ingest.poop_pdf_importer import (
    extract_records_from_pdf,
    import_seed_sources,
    import_poops_from_directory,
)


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


class _FakeAdapter:
    def generate(self, prompt: str, system_prompt: str) -> str:
        if "source_type: best_practices" in prompt:
            return """
            [
              {
                "name": "DevOps",
                "element_type": "discipline",
                "part": "variative",
                "credits": 5,
                "semesters": [6],
                "competency_codes": ["ОПК-2", "ОПК-8", "ПК-11", "ПК-14", "ПК-7", "УК-6"],
                "practice_type": null,
                "fgos_mandatory": null
              }
            ]
            """.strip()
        return """
        [
          {
            "name": "Технологическая практика",
            "element_type": "practice",
            "part": "mandatory",
            "credits": 6,
            "semesters": [6],
            "competency_codes": ["ОПК-2", "ОПК-8"],
            "practice_type": "industrial",
            "fgos_mandatory": null
          }
        ]
        """.strip()


def test_import_poops_from_directory_uses_llm_fallback_for_empty_pdf() -> None:
    workspace = Path("tests/.tmp/poop_llm_fallback")
    if workspace.exists():
        shutil.rmtree(workspace)
    input_dir = workspace / "poop_pdf"
    input_dir.mkdir(parents=True)
    (input_dir / "010302_POOP_B.pdf").write_bytes(Path("backend/seed/poop_pdf/010302_POOP_B.pdf").read_bytes())
    output_path = workspace / "poop_disciplines.json"

    try:
        records = import_poops_from_directory(
            input_dir=input_dir,
            output_path=output_path,
            strategy="hybrid",
            adapter=_FakeAdapter(),
        )

        assert len(records) == 1
        assert records[0].source_name == "010302_POOP_B.pdf"
        assert records[0].element_type == "practice"
        assert records[0].practice_type == "industrial"

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload[0]["direction_code"] == "010302"
        assert payload[0]["name"] == "Технологическая практика"
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

    (poop_dir / "010302_POOP_B.pdf").write_bytes(Path("backend/seed/poop_pdf/010302_POOP_B.pdf").read_bytes())
    source_best_pdf = next(Path("backend/seed/best_practices_pdf").glob("*.pdf"))
    (best_practices_dir / source_best_pdf.name).write_bytes(source_best_pdf.read_bytes())
    output_path = workspace / "poop_disciplines.json"

    try:
        records = import_seed_sources(
            output_path=output_path,
            strategy="hybrid",
            adapter=_FakeAdapter(),
            source_dirs={
                "poop": poop_dir,
                "best_practices": best_practices_dir,
            },
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
