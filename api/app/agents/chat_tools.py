from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Card, Deck
from app.schemas import DeckSuggestionRequest
from app.services.deck_service import (
    analyze_deck_data,
    check_deck_rules_data,
    diagnose_deck_data,
    get_deck_card_rows,
    get_deck_or_404,
    serialize_card,
    serialize_deck,
    suggest_cards_for_deck,
)
from app.services.price_service import get_deck_price, search_card_prices
from app.vector import ensure_collection, semantic_search_cards

DECK_TOOL_NAMES = {
    "list_decks",
    "get_deck",
    "analyze_deck",
    "check_deck_rules",
    "diagnose_deck",
    "suggest_cards_for_deck",
    "get_deck_price",
}

CHAT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "list_decks",
        "description": "List decks in the user's local deck database. Use when the user asks what decks they have or refers ambiguously to their decks.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of decks to return.",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 50,
                }
            },
            "required": [],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_deck",
        "description": "Get one deck and its card list from the local database.",
        "parameters": {
            "type": "object",
            "properties": {
                "deck_id": {"type": "integer", "description": "The local deck id."}
            },
            "required": ["deck_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "analyze_deck",
        "description": "Analyze deck stats such as total cards, lands, mana curve, card types, and color identity counts.",
        "parameters": {
            "type": "object",
            "properties": {
                "deck_id": {"type": "integer", "description": "The local deck id."}
            },
            "required": ["deck_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "check_deck_rules",
        "description": "Check basic deck construction rules, especially Commander size, commander presence, singleton, and color identity.",
        "parameters": {
            "type": "object",
            "properties": {
                "deck_id": {"type": "integer", "description": "The local deck id."}
            },
            "required": ["deck_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "diagnose_deck",
        "description": "Diagnose likely deck weaknesses such as land count, ramp, card draw, interaction, board wipes, and curve.",
        "parameters": {
            "type": "object",
            "properties": {
                "deck_id": {"type": "integer", "description": "The local deck id."}
            },
            "required": ["deck_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "suggest_cards_for_deck",
        "description": "Suggest cards for a deck using the local semantic/vector search system, filtered against the deck's existing colors by default.",
        "parameters": {
            "type": "object",
            "properties": {
                "deck_id": {"type": "integer", "description": "The local deck id."},
                "goal": {
                    "type": ["string", "null"],
                    "description": "What the user wants to improve, e.g. ramp, draw, removal, lifegain payoffs, budget upgrades.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of suggestions to return.",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
                "max_mana_value": {
                    "type": ["number", "null"],
                    "description": "Optional maximum mana value for suggestions.",
                },
            },
            "required": ["deck_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "search_cards",
        "description": "Search the local card database by name, rules text, color identity, and/or maximum mana value.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": ["string", "null"], "description": "Name substring."},
                "text": {"type": ["string", "null"], "description": "Oracle/rules text substring."},
                "color": {"type": ["string", "null"], "description": "One color identity letter, such as W, U, B, R, or G."},
                "max_mana_value": {"type": ["number", "null"], "description": "Optional maximum mana value."},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            },
            "required": [],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "search_cards_semantic",
        "description": "Semantic/vector search over the local card database. Use for concept searches like 'cheap lifegain payoff' or 'graveyard hate in white'.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Semantic search query."},
                "color": {"type": ["string", "null"], "description": "One color identity letter, such as W, U, B, R, or G."},
                "max_mana_value": {"type": ["number", "null"], "description": "Optional maximum mana value."},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_deck_price",
        "description": "Estimate a deck's total local price using the locally refreshed Scryfall price columns.",
        "parameters": {
            "type": "object",
            "properties": {
                "deck_id": {"type": "integer", "description": "The local deck id."},
                "price": {
                    "type": "string",
                    "enum": ["usd", "usd_foil", "usd_etched", "eur", "eur_foil", "eur_etched", "tix"],
                    "default": "usd",
                },
            },
            "required": ["deck_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "search_card_prices",
        "description": "Look up local card prices by names or ids. Uses locally refreshed price data, not live external calls.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": ["string", "null"], "description": "Single name substring."},
                "names": {"type": "array", "items": {"type": "string"}, "description": "Exact-ish card names."},
                "ids": {"type": "array", "items": {"type": "integer"}, "description": "Local card ids."},
                "limit": {"type": "integer", "default": 25, "minimum": 1, "maximum": 50},
            },
            "required": [],
            "additionalProperties": False,
        },
        "strict": False,
    },
]


def available_tool_schemas(*, allow_deck_tools: bool) -> list[dict[str, Any]]:
    if allow_deck_tools:
        return CHAT_TOOL_SCHEMAS
    return [tool for tool in CHAT_TOOL_SCHEMAS if tool["name"] not in DECK_TOOL_NAMES]


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    return value


def tool_result_json(value: Any) -> str:
    return json.dumps(json_safe(value), ensure_ascii=False)


def execute_chat_tool(
    *,
    db: Session,
    tool_name: str,
    arguments: dict[str, Any],
    allow_deck_tools: bool,
) -> dict[str, Any]:
    if tool_name in DECK_TOOL_NAMES and not allow_deck_tools:
        raise PermissionError(
            "Deck database tools are disabled for this message. Ask the user to enable deck context."
        )

    if tool_name == "list_decks":
        limit = _bounded_int(arguments.get("limit", 20), default=20, minimum=1, maximum=50)
        decks = db.scalars(select(Deck).order_by(Deck.created_at.desc()).limit(limit)).all()
        return {"decks": [serialize_deck(deck) for deck in decks]}

    if tool_name == "get_deck":
        deck_id = _required_int(arguments, "deck_id")
        deck = get_deck_or_404(db, deck_id)
        rows = get_deck_card_rows(db, deck_id)
        return {
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

    if tool_name == "analyze_deck":
        deck_id = _required_int(arguments, "deck_id")
        deck = get_deck_or_404(db, deck_id)
        return analyze_deck_data(deck=deck, rows=get_deck_card_rows(db, deck_id))

    if tool_name == "check_deck_rules":
        deck_id = _required_int(arguments, "deck_id")
        deck = get_deck_or_404(db, deck_id)
        return check_deck_rules_data(deck=deck, rows=get_deck_card_rows(db, deck_id))

    if tool_name == "diagnose_deck":
        deck_id = _required_int(arguments, "deck_id")
        deck = get_deck_or_404(db, deck_id)
        return diagnose_deck_data(deck=deck, rows=get_deck_card_rows(db, deck_id))

    if tool_name == "suggest_cards_for_deck":
        deck_id = _required_int(arguments, "deck_id")
        deck = get_deck_or_404(db, deck_id)
        request = DeckSuggestionRequest(
            goal=_optional_str(arguments.get("goal")),
            limit=_bounded_int(arguments.get("limit", 5), default=5, minimum=1, maximum=20),
            max_mana_value=_optional_float(arguments.get("max_mana_value")),
            color_identity=None,
        )
        return suggest_cards_for_deck(
            deck=deck,
            rows=get_deck_card_rows(db, deck_id),
            request=request,
            db=db,
        )

    if tool_name == "search_cards":
        limit = _bounded_int(arguments.get("limit", 10), default=10, minimum=1, maximum=50)
        stmt = select(Card)
        name = _optional_str(arguments.get("name"))
        text = _optional_str(arguments.get("text"))
        color = _optional_str(arguments.get("color"))
        max_mana_value = _optional_float(arguments.get("max_mana_value"))
        if name:
            stmt = stmt.where(Card.name.ilike(f"%{name}%"))
        if text:
            stmt = stmt.where(Card.oracle_text.ilike(f"%{text}%"))
        if max_mana_value is not None:
            stmt = stmt.where(Card.mana_value <= max_mana_value)
        if color:
            stmt = stmt.where(Card.color_identity.contains([color.upper()]))
        cards = db.scalars(stmt.order_by(Card.name).limit(limit)).all()
        return {"cards": [serialize_card(card) for card in cards]}

    if tool_name == "search_cards_semantic":
        query = _required_str(arguments, "query")
        limit = _bounded_int(arguments.get("limit", 10), default=10, minimum=1, maximum=50)
        color = _optional_str(arguments.get("color"))
        max_mana_value = _optional_float(arguments.get("max_mana_value"))
        ensure_collection(recreate=False)
        candidate_limit = max(limit * 5, 50)
        qdrant_results = semantic_search_cards(query=query, limit=candidate_limit)
        card_ids = [int(point.id) for point in qdrant_results]
        score_by_id = {int(point.id): point.score for point in qdrant_results}
        stmt = select(Card).where(Card.id.in_(card_ids))
        if color:
            stmt = stmt.where(Card.color_identity.contains([color.upper()]))
        if max_mana_value is not None:
            stmt = stmt.where(Card.mana_value <= max_mana_value)
        cards = db.scalars(stmt).all()
        card_by_id = {card.id: card for card in cards}
        ranked_cards = [card_by_id[card_id] for card_id in card_ids if card_id in card_by_id][:limit]
        return {
            "query": query,
            "cards": [
                {**serialize_card(card), "score": score_by_id.get(card.id)}
                for card in ranked_cards
            ],
        }

    if tool_name == "get_deck_price":
        deck_id = _required_int(arguments, "deck_id")
        price = _optional_str(arguments.get("price")) or "usd"
        return get_deck_price(db, deck_id, price=price)

    if tool_name == "search_card_prices":
        return {
            "prices": search_card_prices(
                db,
                name=_optional_str(arguments.get("name")),
                names=[str(name) for name in arguments.get("names") or []],
                ids=[int(card_id) for card_id in arguments.get("ids") or []],
                limit=_bounded_int(arguments.get("limit", 25), default=25, minimum=1, maximum=50),
            )
        }

    raise ValueError(f"Unknown chat tool: {tool_name}")


def summarize_tool_result(tool_name: str, result: dict[str, Any]) -> str:
    if tool_name == "list_decks":
        return f"returned {len(result.get('decks', []))} deck(s)"
    if tool_name == "get_deck":
        deck = result.get("deck") or {}
        cards = result.get("cards") or []
        total = sum(int(item.get("quantity") or 0) for item in cards)
        return f"loaded {deck.get('name', 'deck')} with {total} card(s)"
    if tool_name == "analyze_deck":
        summary = result.get("summary") or {}
        return f"analyzed {summary.get('total_cards', 0)} card(s), average MV {summary.get('average_mana_value') or '-'}"
    if tool_name == "check_deck_rules":
        issues = result.get("issues") or []
        return f"valid={result.get('is_valid')}; {len(issues)} issue(s)"
    if tool_name == "diagnose_deck":
        findings = result.get("findings") or []
        return f"found {len(findings)} diagnosis finding(s)"
    if tool_name == "suggest_cards_for_deck":
        suggestions = result.get("suggestions") or []
        return f"returned {len(suggestions)} suggestion(s)"
    if tool_name in {"search_cards", "search_cards_semantic"}:
        return f"returned {len(result.get('cards', []))} card(s)"
    if tool_name == "get_deck_price":
        return f"estimated total {result.get('total_estimate')} {result.get('price_field', 'usd')}"
    if tool_name == "search_card_prices":
        return f"returned {len(result.get('prices', []))} price record(s)"
    return "completed"


def error_to_result(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, HTTPException):
        return {"error": exc.detail, "status_code": exc.status_code}
    return {"error": f"{exc.__class__.__name__}: {exc}"}


def _required_int(arguments: dict[str, Any], key: str) -> int:
    if key not in arguments or arguments[key] is None:
        raise ValueError(f"Missing required argument: {key}")
    return int(arguments[key])


def _required_str(arguments: dict[str, Any], key: str) -> str:
    value = _optional_str(arguments.get(key))
    if not value:
        raise ValueError(f"Missing required argument: {key}")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))
