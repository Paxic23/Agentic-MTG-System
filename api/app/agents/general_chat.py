from __future__ import annotations

import json
from typing import Any

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.chat_tools import (
    available_tool_schemas,
    error_to_result,
    execute_chat_tool,
    json_safe,
    summarize_tool_result,
    tool_result_json,
)
from app.core.config import get_settings
from app.llm.factory import get_llm_client
from app.llm.prompts.general_chat import build_general_chat_prompts
from app.models import Card, Deck, DeckCard
from app.schemas import GeneralChatRequest, GeneralChatResponse
from app.services.deck_service import serialize_card, serialize_deck

MAX_TOOL_ROUNDS = 6


class GeneralChatAgent:
    def run(self, *, request: GeneralChatRequest, db: Session) -> GeneralChatResponse:
        settings = get_settings()
        provider = settings.llm_provider.lower().strip()

        if provider in {"", "none", "off", "disabled"} or not settings.llm_model:
            return GeneralChatResponse(
                reply=(
                    "General chat is currently disabled because no LLM provider is configured. "
                    "Set LLM_PROVIDER and LLM_MODEL in the API environment to enable it."
                ),
                used_deck_context=False,
                referenced_deck_count=0,
                tool_trace=[],
            )

        if provider == "openai":
            return self._run_openai_agent(request=request, db=db)

        # Local models are kept prompt-only for now. We can add a native Ollama
        # tool loop later once the selected local model reliably emits structured
        # tool calls.
        return self._run_prompt_only_fallback(request=request, db=db)

    def _run_openai_agent(self, *, request: GeneralChatRequest, db: Session) -> GeneralChatResponse:
        settings = get_settings()
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY must be set when LLM_PROVIDER=openai")

        client = OpenAI(api_key=settings.llm_api_key, timeout=settings.llm_timeout_seconds)
        allow_deck_tools = bool(request.include_deck_context)
        tools = available_tool_schemas(allow_deck_tools=allow_deck_tools)
        tool_trace: list[dict[str, Any]] = []

        response = client.responses.create(
            model=settings.llm_model,
            instructions=self._build_instructions(request=request, allow_deck_tools=allow_deck_tools),
            input=self._messages_as_response_input(request),
            tools=tools,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
        )

        for _ in range(MAX_TOOL_ROUNDS):
            tool_calls = self._get_tool_calls(response)
            if not tool_calls:
                return GeneralChatResponse(
                    reply=self._extract_output_text(response),
                    used_deck_context=allow_deck_tools,
                    referenced_deck_count=self._referenced_deck_count(request, tool_trace),
                    tool_trace=tool_trace,
                )

            tool_outputs = []
            for call in tool_calls:
                tool_name = getattr(call, "name", "")
                call_id = getattr(call, "call_id", None)
                raw_args = getattr(call, "arguments", "{}") or "{}"
                try:
                    arguments = json.loads(raw_args)
                    result = execute_chat_tool(
                        db=db,
                        tool_name=tool_name,
                        arguments=arguments,
                        allow_deck_tools=allow_deck_tools,
                    )
                    ok = True
                    summary = summarize_tool_result(tool_name, result)
                    error = None
                except Exception as exc:
                    arguments = _safe_args(raw_args)
                    result = error_to_result(exc)
                    ok = False
                    summary = None
                    error = result.get("error") or f"{exc.__class__.__name__}: {exc}"

                tool_trace.append(
                    {
                        "tool": tool_name,
                        "arguments": json_safe(arguments),
                        "ok": ok,
                        "summary": summary,
                        "error": error,
                    }
                )
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": tool_result_json(result),
                    }
                )

            response = client.responses.create(
                model=settings.llm_model,
                instructions=self._build_instructions(request=request, allow_deck_tools=allow_deck_tools),
                input=tool_outputs,
                previous_response_id=response.id,
                tools=tools,
                temperature=settings.llm_temperature,
                max_output_tokens=settings.llm_max_output_tokens,
            )

        return GeneralChatResponse(
            reply=(
                self._extract_output_text(response)
                or "I used several tools, but stopped before completing to avoid an infinite tool loop. Please ask a narrower question."
            ),
            used_deck_context=allow_deck_tools,
            referenced_deck_count=self._referenced_deck_count(request, tool_trace),
            tool_trace=tool_trace,
        )

    def _run_prompt_only_fallback(self, *, request: GeneralChatRequest, db: Session) -> GeneralChatResponse:
        settings = get_settings()
        llm_client = get_llm_client(settings)
        if not llm_client.is_enabled:
            return GeneralChatResponse(
                reply=(
                    "General chat is currently disabled because no LLM provider is configured. "
                    "Set LLM_PROVIDER and LLM_MODEL in the API environment to enable it."
                ),
                used_deck_context=False,
                referenced_deck_count=0,
                tool_trace=[],
            )

        deck_context = self._build_deck_context(
            db=db,
            include_deck_context=request.include_deck_context,
            deck_ids=request.deck_ids,
        )
        messages = [{"role": message.role, "content": message.content} for message in request.messages]
        system_prompt, user_prompt = build_general_chat_prompts(messages=messages, deck_context=deck_context)
        completion = llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
        )
        return GeneralChatResponse(
            reply=completion.text,
            used_deck_context=deck_context is not None,
            referenced_deck_count=len(deck_context or []),
            tool_trace=[
                {
                    "tool": "prompt_only_fallback",
                    "arguments": {"provider": settings.llm_provider, "model": settings.llm_model},
                    "ok": True,
                    "summary": "local/non-OpenAI provider used without tool calling",
                    "error": None,
                }
            ],
        )

    def _build_instructions(self, *, request: GeneralChatRequest, allow_deck_tools: bool) -> str:
        deck_context_text = (
            "Deck database tools are ENABLED for this message. Use deck_ids as the likely active/current deck ids: "
            f"{request.deck_ids or 'none provided; call list_decks if needed'}."
            if allow_deck_tools
            else "Deck database tools are DISABLED for this message. Do not claim to inspect the user's local decks. Ask the user to enable deck context if local deck data is needed."
        )
        return f"""
You are an agentic Magic: The Gathering assistant inside a local deck-building app.

Use tools whenever the user asks about cards in the local database, card suggestions, prices, rules checks, deck weaknesses, Commander legality, color identity, or their local decks.

{deck_context_text}

Rules:
- Do not claim you searched, analyzed, diagnosed, priced, or checked anything unless you actually used a tool.
- Do not invent local deck contents. If deck data is needed and tools are enabled, call the relevant deck tool.
- You may recommend deck changes, but you are read-only. You cannot add/remove cards or edit decks.
- Be explicit about uncertainty when local data, prices, or vector results are missing.
- For theme/tag judgments, distinguish core themes from incidental mentions. Do not call a deck a graveyard/sacrifice/token/lifegain deck just because one or two cards mention that concept.
- Keep answers practical and concise. Use card names from tool results when making card-specific claims.
""".strip()

    def _messages_as_response_input(self, request: GeneralChatRequest) -> list[dict[str, str]]:
        return [
            {"role": message.role, "content": message.content}
            for message in request.messages
            if message.content.strip()
        ]

    def _get_tool_calls(self, response: Any) -> list[Any]:
        return [
            item
            for item in getattr(response, "output", []) or []
            if getattr(item, "type", None) == "function_call"
        ]

    def _extract_output_text(self, response: Any) -> str:
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()

        parts: list[str] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "message":
                continue
            for content in getattr(item, "content", []) or []:
                content_type = getattr(content, "type", None)
                if content_type in {"output_text", "text"}:
                    value = getattr(content, "text", None)
                    if value:
                        parts.append(value)
        return "\n".join(parts).strip()

    def _referenced_deck_count(self, request: GeneralChatRequest, tool_trace: list[dict[str, Any]]) -> int:
        deck_ids = set(request.deck_ids or [])
        for entry in tool_trace:
            arguments = entry.get("arguments") or {}
            deck_id = arguments.get("deck_id")
            if deck_id is not None:
                try:
                    deck_ids.add(int(deck_id))
                except (TypeError, ValueError):
                    pass
        return len(deck_ids)

    def _build_deck_context(
        self,
        *,
        db: Session,
        include_deck_context: bool,
        deck_ids: list[int],
    ) -> list[dict[str, Any]] | None:
        if not include_deck_context:
            return None

        if deck_ids:
            decks = db.scalars(
                select(Deck).where(Deck.id.in_(deck_ids)).order_by(Deck.created_at.desc())
            ).all()
        else:
            decks = db.scalars(select(Deck).order_by(Deck.created_at.desc())).all()

        context: list[dict[str, Any]] = []
        for deck in decks:
            rows = (
                db.execute(
                    select(DeckCard, Card)
                    .join(Card, DeckCard.card_id == Card.id)
                    .where(DeckCard.deck_id == deck.id)
                    .order_by(Card.name)
                ).all()
            )
            context.append(
                {
                    "deck": serialize_deck(deck),
                    "cards": [
                        {
                            "quantity": deck_card.quantity,
                            "is_commander": deck_card.is_commander,
                            "card": serialize_card(card),
                        }
                        for deck_card, card in rows
                    ],
                }
            )
        return context


def _safe_args(raw_args: str) -> dict[str, Any]:
    try:
        value = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return {"_raw": raw_args}
    return value if isinstance(value, dict) else {"_raw": value}
