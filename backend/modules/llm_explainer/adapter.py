import json
import os
from urllib import error, request


class LLMAdapterError(Exception):
    """Raised when the local LLM backend is unavailable or returns invalid data."""


class OllamaAdapter:
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: int = 120) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3:latest")
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", str(timeout)))

    def generate(self, prompt: str, system_prompt: str) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "num_ctx": 8192,   # expand context window; model supports up to 8192
                    "temperature": 0.1, # low temp = more factual, less creative hallucination
                },
            }
        ).encode("utf-8")
        http_request = request.Request(
            url=f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except error.URLError as exc:
            raise LLMAdapterError(f"Ollama is unavailable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMAdapterError("Ollama request timed out") from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMAdapterError("Ollama returned invalid JSON") from exc

        text = str(data.get("response", "")).strip()
        if not text:
            raise LLMAdapterError("Ollama returned an empty response")
        return text
