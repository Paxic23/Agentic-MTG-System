from __future__ import annotations

import json
from typing import Any

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.chat_tools import CHAT_TOOL_SCHEMAS, execute_chat_tool
from app.core.config import get_settings
from app.llm.factory import get_llm_client
from app.llm.prompts.general_chat import build_general_chat_prompts
from app.models import Deck
from app.schemas import GeneralChatRequest, GeneralChatResponse
from app.services.deck_service import get_deck_card_rows, serialize_card, serialize_deck

MAX_AGENT_STEPS = 6
MAX_TOOL_OUTPUT_CHARS = 16_000


AGENT_INSTRUCTIONS = """
You are an expert Magic: The Gathering assistant inside a local deck-building app.

You have read-only tools for local decks, cards, deck analysis, rules checks, semantic card search, suggestions, and prices.

Use tools when the user's question depends on their local deck database, card database, semantic search, or local price data. Do not guess deck contents, prices, legality, color identity, or card text when a tool can check it.

The current version is read-only. If the user asks you to add, remove, import, delete, or change cards/decks, recommend the change and say it needs confirmation/UI support before applying.

When discussing themes, distinguish between core themes, secondary themes, and incidental mentions. Do not call a deck a sacrifice, graveyard, token, lifegain, or other themed deck just because one or two cards mention that mechanic.

Give practical, concise answers. Prefer concrete card names, reasons, and tradeoffs. Mention uncertainty when the available local data is incomplete.
""".strip()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _summarize_result(result: Any) -> str:
    if isinstance(result, list):
        return f"returned {len(result)} item(s)"
    if isinstance(result, dict):
        if "deck_name" in result and "total_estimate" in result:
            return f"estimated {result.get('deck_name')} at {result.get('total_estimate')} {result.get('price_field')}"
        if "suggestions" in result:
            return f"returned {len(result.get('suggestions') or [])} suggestion(s)"
        if "summary" in result:
            return "returned deck summary/analysis"
        if "issues" in result:
            return f"returned {len(result.get('issues') or [])} rules issue(s)"
        if "cards" in result:
            return f"returned deck with {len(result.get('cards') or [])} card row(s)"
    return "returned result"


def _active_deck_hint(request: GeneralChatRequest, db: Session) -> str:
    if not request.include_deck_context:
        return "Deck context toggle is OFF. Only inspect local decks if the user explicitly asks you to."

    if request.deck_ids:
        decks = db.scalars(select(Deck).where(Deck.id.in_(request.deck_ids))).all()
        deck_names = ", ".join(f"{deck.id}: {deck.name}" for deck in decks) or "none found"
        return f"Deck context toggle is ON. The selected/active deck ids are: {deck_names}. For 'my deck' or 'this deck', prefer these decks."

    decks = db.scalars(select(Deck).order_by(Deck.created_at.desc()).limit(25)).all()
    deck_names = ", ".join(f"{deck.id}: {deck.name}" for deck in decks) or "none found"
    return f"Deck context toggle is ON for all decks. Available recent decks: {deck_names}."


def _build_deck_context_for_fallback(
    *,
    db: Session,
    include_deck_context: bool,
    deck_ids: list[int],
) -> list[dict[str, Any]] | None:
    if not include_deck_context:
        return None

    if deck_ids:
        decks = db.scalars(select(Deck).where(Deck.id.in_(deck_ids)).order_by(Deck.created_at.desc())).all()
    else:
        decks = db.scalars(select(Deck).order_by(Deck.created_at.desc())).all()

    context: list[dict[str, Any]] = []
    for deck in decks:
        rows = get_deck_card_rows(db, deck.id)
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


class GeneralChatAgent:
    def run(self, *, request: GeneralChatRequest, db: Session) -> GeneralChatResponse:
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
            )

        # The first agentic implementation uses OpenAI's Responses API.
        # Keep the old prompt-only path for Ollama/openai-compatible providers.
        if settings.llm_provider.lower().strip() != "openai":
            return self._run_prompt_only_fallback(request=request, db=db)

        return self._run_openai_responses_agent(request=request, db=db)

    def _run_prompt_only_fallback(self, *, request: GeneralChatRequest, db: Session) -> GeneralChatResponse:
        settings = get_settings()
        llm_client = get_llm_client(settings)
        deck_context = _build_deck_context_for_fallback(
            db=db,
            include_deck_context=request.include_deck_context,
            deck_ids=request.deck_ids,
        )
        messages = [{"role": message.role, "content": message.content} for message in request.messages]
        system_prompt, user_prompt = build_general_chat_prompts(
            messages=messages,
            deck_context=deck_context,
        )
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
            used_agentic_tools=False,
            tool_trace=[],
        )

    def _run_openai_responses_agent(self, *, request: GeneralChatRequest, db: Session) -> GeneralChatResponse:
        settings = get_settings()
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY must be set when LLM_PROVIDER=openai")

        client = OpenAI(api_key=settings.llm_api_key, timeout=settings.llm_timeout_seconds)
        tool_trace: list[dict[str, Any]] = []

        instructions = f"{AGENT_INSTRUCTIONS}\n\nApplication context: {_active_deck_hint(request, db)}"
        input_items: list[Any] = [
            {"role": message.role, "content": message.content}
            for message in request.messages
            if message.content.strip()
        ]

        response = None
        for _step in range(MAX_AGENT_STEPS):
            response = client.responses.create(
                model=settings.llm_model,
                instructions=instructions,
                input=input_items,
                tools=CHAT_TOOL_SCHEMAS,
                max_output_tokens=settings.llm_max_output_tokens,
                store=False,
            )

            function_calls = [item for item in response.output if getattr(item, "type", None) == "function_call"]
            if not function_calls:
                reply = (response.output_text or "").strip()
                return GeneralChatResponse(
                    reply=reply or "I could not produce a response.",
                    used_deck_context=request.include_deck_context,
                    referenced_deck_count=len(request.deck_ids),
                    used_agentic_tools=bool(tool_trace),
                    tool_trace=tool_trace,
                )

            # Preserve reasoning/function_call items before adding function_call_output items.
            input_items += response.output

            for call in function_calls:
                raw_args = getattr(call, "arguments", "{}") or "{}"
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}

                try:
                    result = execute_chat_tool(db, call.name, args)
                    ok = True
                    output = _json_dumps(result)
                    summary = _summarize_result(result)
                except Exception as exc:
                    ok = False
                    output = _json_dumps({"error": f"{exc.__class__.__name__}: {exc}"})
                    summary = f"failed: {exc.__class__.__name__}"

                if len(output) > MAX_TOOL_OUTPUT_CHARS:
                    output = output[:MAX_TOOL_OUTPUT_CHARS] + "... [truncated]"

                tool_trace.append(
                    {
                        "tool": call.name,
                        "args": args,
                        "ok": ok,
                        "summary": summary,
                    }
                )
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": output,
                    }
                )

        return GeneralChatResponse(
            reply=(
                "I started checking this with the available tools, but hit the tool-call limit before finishing. "
                "Try asking a narrower question, such as one deck, one problem, or one card category."
            ),
            used_deck_context=request.include_deck_context,
            referenced_deck_count=len(request.deck_ids),
            used_agentic_tools=bool(tool_trace),
            tool_trace=tool_trace,
        )