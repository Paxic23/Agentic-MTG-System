import json
from typing import Any


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _format_messages(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []

    for message in messages:
        role = message.get("role", "user").strip().lower()
        content = (message.get("content") or "").strip()

        if not content:
            continue

        speaker = "User" if role == "user" else "Assistant"
        lines.append(f"{speaker}: {content}")

    return "\n\n".join(lines)


def build_general_chat_prompts(
    *,
    messages: list[dict[str, str]],
    deck_context: list[dict[str, Any]] | None,
    tool_context: dict[str, Any] | None = None,
) -> tuple[str, str]:
    system_prompt = (
        "You are a friendly, expert Magic: The Gathering chat assistant. "
        "Be conversational and direct, without rigid templates. "
        "Answer the user's MTG questions naturally. "
        "Only use deck database context if it is provided in the prompt. "
        "If deck context is not provided, never assume deck contents. "
        "If uncertain, state uncertainty clearly and suggest practical next checks."
    )

    transcript = _format_messages(messages)
    deck_context_text = _compact_json(deck_context) if deck_context is not None else "none"
    tool_context_text = _compact_json(tool_context) if tool_context is not None else "none"

    user_prompt = f"""
Continue this MTG conversation.

Conversation transcript:
{transcript or "User: (no message provided)"}

Deck database context (optional):
{deck_context_text}

Agentic tool context (optional):
{tool_context_text}

Instructions:
- Respond as the assistant's next message only.
- Keep a natural chat tone.
- Use short paragraphs or bullets only if they help clarity.
- If deck context is provided, you may reference those decks directly.
- If deck context is none, avoid claims about what is in the user's decks.
- If agentic tool context is provided, treat it as authoritative structured data.
""".strip()

    return system_prompt, user_prompt
