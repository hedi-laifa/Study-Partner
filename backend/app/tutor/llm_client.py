"""Configurable Ollama LLM service abstraction with timeouts, error handling, and structured outputs."""
import json
import re
from typing import TypeVar

from fastapi import status
import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)


class LLMServiceUnavailableError(AppException):
    """Raised when the Ollama runtime is unreachable, times out, or the requested model is unavailable."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            detail=detail,
            error_code="LLM_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class LLMOutputValidationError(AppException):
    """Raised when the LLM fails to return valid structured JSON matching the target schema."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            detail=detail,
            error_code="LLM_OUTPUT_VALIDATION_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


def _extract_json_object(raw_text: str) -> str:
    """Extract a JSON object from raw LLM text, stripping optional markdown code fences."""
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return cleaned[first_brace : last_brace + 1]
    return cleaned


class OllamaLLMClient:
    """Configurable client for local Ollama inference supporting timeouts and structured Pydantic outputs."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.OLLAMA_TIMEOUT_SECONDS
        )

    def _post_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        json_mode: bool = True,
    ) -> str:
        """Send a synchronous chat completion request to Ollama `/api/chat`."""
        url = f"{self.base_url}/api/chat"
        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            logger.warning(
                f"Ollama request timed out after {self.timeout_seconds}s (model={self.model})"
            )
            raise LLMServiceUnavailableError(
                f"Ollama model '{self.model}' timed out after {self.timeout_seconds} seconds."
            ) from exc
        except httpx.RequestError as exc:
            logger.warning(
                f"Unable to connect to Ollama at '{self.base_url}': {exc}"
            )
            raise LLMServiceUnavailableError(
                f"Ollama service at '{self.base_url}' is unreachable ({exc})."
            ) from exc

        if response.status_code == status.HTTP_404_NOT_FOUND:
            raise LLMServiceUnavailableError(
                f"Ollama model '{self.model}' is not available or not pulled at '{self.base_url}'."
            )
        if response.status_code >= 400:
            raise LLMServiceUnavailableError(
                f"Ollama returned HTTP {response.status_code}: {response.text[:300]}"
            )

        try:
            body = response.json()
            content = body.get("message", {}).get("content", "")
            if not isinstance(content, str) or not content.strip():
                raise LLMOutputValidationError(
                    "Ollama returned an empty message content."
                )
            return content
        except ValueError as exc:
            raise LLMOutputValidationError(
                f"Ollama returned non-JSON HTTP response: {exc}"
            ) from exc

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """Generate an unstructured text response from Ollama."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._post_chat(messages, temperature=temperature, json_mode=False)

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.2,
        max_retries: int = 1,
    ) -> T:
        """Generate a response from Ollama and validate it against `response_model` with repair retry."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            raw_output = self._post_chat(
                messages, temperature=temperature, json_mode=True
            )
            extracted_json = _extract_json_object(raw_output)
            try:
                return response_model.model_validate_json(extracted_json)
            except (ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning(
                    f"Structured output validation failed on attempt {attempt + 1}: {exc}"
                )
                if attempt < max_retries:
                    messages.append({"role": "assistant", "content": raw_output})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Your response did not match the required JSON schema. "
                                f"Validation error: {exc}. Return ONLY a valid JSON object matching: "
                                f"{json.dumps(response_model.model_json_schema())}"
                            ),
                        }
                    )

        raise LLMOutputValidationError(
            f"LLM output failed schema validation after {max_retries + 1} attempts: {last_error}"
        )
