from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import DeckCoachRequest, DeckSuggestionRequest
from app.services.deck_service import (
    analyze_deck_data,
    build_deck_coach_report,
    check_deck_rules_data,
    diagnose_deck_data,
    get_deck_card_rows,
    get_deck_or_404,
    serialize_deck,
    suggest_cards_for_deck,
)


router = APIRouter(tags=["agent"])


@router.post("/agent/deck-coach")
def deck_coach_agent(
    request: DeckCoachRequest,
    db: Session = Depends(get_db),
):
    deck = get_deck_or_404(db, request.deck_id)
    rows = get_deck_card_rows(db, request.deck_id)

    if not rows:
        return {
            "deck": serialize_deck(deck),
            "coach_report": (
                f"# Deck Coach Report: {deck.name}\n\n"
                "This deck has no cards yet. Add or import a decklist first, then run the coach again."
            ),
            "tool_payloads": {} if request.include_tool_payloads else None,
        }

    analysis = analyze_deck_data(deck=deck, rows=rows)
    rules_check = check_deck_rules_data(deck=deck, rows=rows)
    diagnosis = diagnose_deck_data(deck=deck, rows=rows)

    suggested_goal = request.goal

    if not suggested_goal:
        for finding in diagnosis.get("findings", []):
            if finding.get("severity") in {"error", "warning", "info"}:
                if finding.get("suggested_goal"):
                    suggested_goal = finding["suggested_goal"]
                    break

    if not suggested_goal:
        themes = diagnosis.get("themes", [])
        if themes:
            suggested_goal = f"cards that support these deck themes: {', '.join(themes[:5])}"
        else:
            suggested_goal = "cards that improve this deck's main strategy"

    suggestions_response = suggest_cards_for_deck(
        deck=deck,
        rows=rows,
        request=DeckSuggestionRequest(
            goal=suggested_goal,
            limit=request.suggestion_limit,
            max_mana_value=request.max_mana_value,
            color_identity=None,
        ),
        db=db,
    )

    coach_report = build_deck_coach_report(
        deck=deck,
        analysis=analysis,
        rules_check=rules_check,
        diagnosis=diagnosis,
        suggestions_response=suggestions_response,
        user_goal=request.goal,
    )

    response = {
        "deck": serialize_deck(deck),
        "goal_used": suggested_goal,
        "coach_report": coach_report,
    }

    if request.include_tool_payloads:
        response["tool_payloads"] = {
            "analysis": analysis,
            "rules_check": rules_check,
            "diagnosis": diagnosis,
            "suggestions": suggestions_response,
        }

    return response
