from dataclasses import dataclass
from typing import Protocol

from openai import BadRequestError, OpenAI


@dataclass(frozen=True)
class LLMCompletion:
    text: str
    provider: str
    model: str


class LLMClient(Protocol):
    provider: str
    model: str
    is_enabled: bool

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_output_tokens: int,
    ) -> LLMCompletion:
        ...


class DisabledLLMClient:
    provider = "none"
    model = ""
    is_enabled = False

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_output_tokens: int,
    ) -> LLMCompletion:
        raise RuntimeError("LLM is disabled")


class OpenAICompatibleLLMClient:
    """Small adapter for OpenAI and OpenAI-compatible endpoints.

    This intentionally avoids LangChain wrappers for now. It keeps provider
    switching simple while still supporting local Ollama through its
    OpenAI-compatible API surface.
    """

    is_enabled = True

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None,
        timeout_seconds: float,
    ) -> None:
        self.provider = provider
        self.model = model
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
        )

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_output_tokens: int,
    ) -> LLMCompletion:
        request_kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        try:
            response = self._client.chat.completions.create(
                **request_kwargs,
                max_tokens=max_output_tokens,
            )
        except BadRequestError as exc:
            message = str(exc).lower()
            if "max_completion_tokens" not in message or "max_tokens" not in message:
                raise

            response = self._client.chat.completions.create(
                **request_kwargs,
                max_completion_tokens=max_output_tokens,
            )

        message = response.choices[0].message
        text = (message.content or "").strip()
        if not text:
            raise RuntimeError("LLM returned an empty response")

        return LLMCompletion(
            text=text,
            provider=self.provider,
            model=self.model,
        )
