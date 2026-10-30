from __future__ import annotations

import json
from dataclasses import dataclass

import httpx


class ModelError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class LLMResult:
    text: str
    model: str


class GroqClient:
    def __init__(self, api_key: str, model: str, base_url: str, timeout: float = 25.0):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, messages: list[dict], temperature: float) -> LLMResult:
        if not self.api_key:
            raise ModelError("Falta GROQ_API_KEY en el servicio.", status_code=503)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 500,
            "reasoning_effort": "low",
        }
        response = self._post(payload)
        if response.status_code == 400 and "reasoning_effort" in response.text:
            payload.pop("reasoning_effort")
            response = self._post(payload)
        if response.status_code >= 400:
            raise ModelError(
                f"El modelo respondió {response.status_code}.",
                status_code=response.status_code,
            )
        body = response.json()
        message = body["choices"][0]["message"]
        text = (message.get("content") or "").strip()
        if not text:
            raise ModelError("El modelo devolvió una respuesta vacía.")
        return LLMResult(text=text, model=body.get("model") or self.model)

    def _post(self, payload: dict) -> httpx.Response:
        try:
            return httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                content=json.dumps(payload),
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise ModelError("El modelo no respondió a tiempo.", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise ModelError("No hubo conexión con el modelo.", status_code=502) from exc
