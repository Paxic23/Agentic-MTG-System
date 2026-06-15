import json
from dataclasses import dataclass
from typing import Any, Protocol

from openai import BadRequestError, OpenAI


@dataclass(frozen=True)
class LLMCompletion:
    text: str
    provider: str
    model: str


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMDecision:
    tool_calls: list[ToolCall]
    text: str | None


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

    def decide_with_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
        max_output_tokens: int,
        force_text: bool = False,
    ) -> LLMDecision:
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

    def decide_with_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
        max_output_tokens: int,
        force_text: bool = False,
    ) -> LLMDecision:
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

    def decide_with_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
        max_output_tokens: int,
        force_text: bool = False,
    ) -> LLMDecision:
        tool_choice = "none" if force_text else "auto"

        request_kwargs = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "temperature": temperature,
        }

        try:
            response = self._client.chat.completions.create(
                **request_kwargs,
                max_tokens=max_output_tokens,
            )
        except BadRequestError as exc:
            message = str(exc).lower()
            if "max_completion_tokens" not in message and "max_tokens" not in message:
                raise

            response = self._client.chat.completions.create(
                **request_kwargs,
                max_completion_tokens=max_output_tokens,
            )

        message = response.choices[0].message

        if message.tool_calls:
            calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                )
                for tc in message.tool_calls
            ]
            return LLMDecision(tool_calls=calls, text=None)

        return LLMDecision(tool_calls=[], text=(message.content or "").strip())
