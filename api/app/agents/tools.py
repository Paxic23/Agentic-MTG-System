from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.factory import get_llm_client
from app.llm.prompts.deck_coach import build_deck_coach_prompts
from app.models import Card, Deck, DeckCard
from app.schemas import DeckSuggestionRequest
from app.services.deck_service import (
    analyze_deck_data,
    build_deck_coach_report,
    check_deck_rules_data,
    diagnose_deck_data,
    suggest_cards_for_deck,
)


DeckRows = list[tuple[DeckCard, Card]]


def run_analysis_tool(deck: Deck, rows: DeckRows) -> dict[str, Any]:
    return analyze_deck_data(deck=deck, rows=rows)


def run_rules_check_tool(deck: Deck, rows: DeckRows) -> dict[str, Any]:
    return check_deck_rules_data(deck=deck, rows=rows)


def run_diagnosis_tool(deck: Deck, rows: DeckRows) -> dict[str, Any]:
    return diagnose_deck_data(deck=deck, rows=rows)


def resolve_coach_goal(user_goal: str | None) -> str | None:
    if user_goal is None:
        return None

    normalized = user_goal.strip()
    return normalized or None


def run_suggestion_tool(
    *,
    deck: Deck,
    rows: DeckRows,
    db: Session,
    goal: str | None,
    limit: int,
    max_mana_value: float | None,
) -> dict[str, Any]:
    request = DeckSuggestionRequest(
        goal=goal,
        limit=limit,
        max_mana_value=max_mana_value,
        color_identity=None,
    )

    return suggest_cards_for_deck(
        deck=deck,
        rows=rows,
        request=request,
        db=db,
    )


def run_report_tool(
    *,
    deck: Deck,
    analysis: dict[str, Any],
    rules_check: dict[str, Any],
    diagnosis: dict[str, Any],
    suggestions_response: dict[str, Any],
    user_goal: str | None,
) -> str:
    return build_deck_coach_report(
        deck=deck,
        analysis=analysis,
        rules_check=rules_check,
        diagnosis=diagnosis,
        suggestions_response=suggestions_response,
        user_goal=user_goal,
    )


def run_llm_report_enhancement_tool(
    *,
    deck: Deck,
    analysis: dict[str, Any],
    rules_check: dict[str, Any],
    diagnosis: dict[str, Any],
    suggestions_response: dict[str, Any],
    goal_used: str | None,
    deterministic_report: str,
) -> dict[str, Any]:
    """Optionally enhance the deterministic report with a configured LLM.

    The endpoint must remain useful without an LLM, so failures fall back to the
    deterministic report instead of breaking the deck-coach route.
    """

    settings = get_settings()
    if not settings.llm_enable_deck_coach:
        return {
            "coach_report": deterministic_report,
            "llm": {
                "enabled": False,
                "used": False,
                "provider": settings.llm_provider,
                "model": settings.llm_model,
            },
        }

    try:
        llm_client = get_llm_client(settings)
        if not llm_client.is_enabled:
            return {
                "coach_report": deterministic_report,
                "llm": {
                    "enabled": False,
                    "used": False,
                    "provider": settings.llm_provider,
                    "model": settings.llm_model,
                },
            }

        system_prompt, user_prompt = build_deck_coach_prompts(
            deck_name=deck.name,
            deck_format=getattr(deck, "format", None),
            goal_used=goal_used,
            analysis=analysis,
            rules_check=rules_check,
            diagnosis=diagnosis,
            suggestions_response=suggestions_response,
            deterministic_report=deterministic_report,
        )

        completion = llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
        )

        return {
            "coach_report": completion.text,
            "llm": {
                "enabled": True,
                "used": True,
                "provider": completion.provider,
                "model": completion.model,
            },
        }

    except Exception as exc:
        return {
            "coach_report": deterministic_report,
            "llm": {
                "enabled": True,
                "used": False,
                "provider": settings.llm_provider,
                "model": settings.llm_model,
                "error": exc.__class__.__name__,
            },
        }
