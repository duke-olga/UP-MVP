from backend.models import CheckReport
from backend.modules.llm_explainer.prompt_builder import SYSTEM_PROMPT, build_user_prompt


def test_build_user_prompt_contains_structured_results() -> None:
    report = CheckReport(
        plan_id=1,
        results=[
            {
                "rule_id": 1,
                "level": "critical",
                "message": "Общий объём программы не соответствует нормативу.",
                "actual": 230,
                "expected": 240,
            },
            {
                "rule_id": 14,
                "level": "critical",
                "message": "Не все компетенции покрыты.",
                "actual": "ПКС-1",
                "expected": "Все компетенции должны быть покрыты",
            },
        ],
    )

    prompt = build_user_prompt(report)

    assert "rule_id=1" in prompt
    assert "rule_id=14" in prompt
    assert "critical" in prompt
    assert "Не придумывай новые нормативы" in prompt
    assert "Формат ответа:" in prompt
    assert "Отвечай строго только на русском языке" in SYSTEM_PROMPT


def test_build_user_prompt_for_clean_report() -> None:
    report = CheckReport(plan_id=1, results=[])

    prompt = build_user_prompt(report)

    assert "без нарушений" in prompt
