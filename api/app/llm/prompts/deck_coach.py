import json
from typing import Any


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def build_deck_coach_prompts(
    *,
    deck_name: str,
    deck_format: str | None,
    goal_used: str | None,
    analysis: dict[str, Any],
    rules_check: dict[str, Any],
    diagnosis: dict[str, Any],
    suggestions_response: dict[str, Any],
    deterministic_report: str,
) -> tuple[str, str]:
    system_prompt = (
        "You are an expert Magic: The Gathering deck coach. "
        "Give practical, format-aware advice in a natural, flexible tone. "
        "Never invent card data not present in the supplied tool outputs. "
        "Prefer clear reasoning, realistic caveats, and concrete next steps."
    )

    user_prompt = f"""
Create a fresh coaching response for this deck.

Deck name: {deck_name}
Format: {deck_format or "unknown"}
Goal used: {goal_used or "none"}

Rules:
- If there are legality or rules issues, surface them early.
- The response can use headings and lists if useful, but do not force a rigid template.
- Keep the response concise but substantive.
- Use only the suggested cards supplied in the tool output.
- Do not claim prices or current market info unless explicitly provided.
- If no explicit goal is provided, do an open-ended deck improvement pass.

Analysis tool output:
{_compact_json(analysis)}

Rules-check tool output:
{_compact_json(rules_check)}

Diagnosis tool output:
{_compact_json(diagnosis)}

Suggestions tool output:
{_compact_json(suggestions_response)}

Deterministic baseline report (optional context, do not feel forced to mirror its structure):
{deterministic_report}
""".strip()

    return system_prompt, user_prompt
