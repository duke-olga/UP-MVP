from backend.models import CheckReport
from backend.modules.llm_explainer.adapter import LLMAdapterError, OllamaAdapter
from backend.modules.llm_explainer.prompt_builder import SYSTEM_PROMPT, build_user_prompt


def generate_recommendations(report: CheckReport, adapter: OllamaAdapter | None = None) -> str:
    if not report.results:
        return "Нарушений не обнаружено. Дополнительные рекомендации LLM не требуются."

    active_adapter = adapter or OllamaAdapter()
    try:
        return active_adapter.generate(
            prompt=build_user_prompt(report),
            system_prompt=SYSTEM_PROMPT,
        )
    except LLMAdapterError as exc:
        return f"LLM недоступна. Сохранен только детерминированный отчет. Причина: {exc}"
