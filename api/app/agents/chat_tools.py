from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Card, Deck, DeckCard
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
from app.services.price_service import get_card_price, get_deck_price, search_card_prices
from app.vector import ensure_collection, semantic_search_cards

MAX_TOOL_LIMIT = 50


def _limit(value: Any, default: int = 10, maximum: int = MAX_TOOL_LIMIT) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def _deck_with_cards(db: Session, deck_id: int) -> dict[str, Any]:
    deck = get_deck_or_404(db, deck_id)
    rows = (
        db.execute(
            select(DeckCard, Card)
            .join(Card, DeckCard.card_id == Card.id)
            .where(DeckCard.deck_id == deck_id)
            .order_by(DeckCard.is_commander.desc(), Card.name)
        )
        .all()
    )
    return {
        **serialize_deck(deck),
        "cards": [
            {
                "quantity": deck_card.quantity,
                "is_commander": deck_card.is_commander,
                "card": serialize_card(card),
            }
            for deck_card, card in rows
        ],
    }


CHAT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "list_decks",
        "description": "List the user's local decks. Use this before choosing a deck when the user did not specify one.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum decks to return."},
            },
            "required": [],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_deck",
        "description": "Get one local deck with its card list, quantities, and commander flags.",
        "parameters": {
            "type": "object",
            "properties": {
                "deck_id": {"type": "integer"},
            },
            "required": ["deck_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "analyze_deck",
        "description": "Compute deck stats such as total cards, lands, mana curve, type counts, and colors.",
        "parameters": {
            "type": "object",
            "properties": {"deck_id": {"type": "integer"}},
            "required": ["deck_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "check_deck_rules",
        "description": "Check basic Commander legality: deck size, commander, singleton, and color identity.",
        "parameters": {
            "type": "object",
            "properties": {"deck_id": {"type": "integer"}},
            "required": ["deck_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "diagnose_deck",
        "description": "Diagnose deck construction issues like low lands, low ramp, low draw, weak interaction, and curve problems.",
        "parameters": {
            "type": "object",
            "properties": {"deck_id": {"type": "integer"}},
            "required": ["deck_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "suggest_cards_for_deck",
        "description": "Suggest cards for a deck using local semantic card search and deck context.",
        "parameters": {
            "type": "object",
            "properties": {
                "deck_id": {"type": "integer"},
                "goal": {"type": "string", "description": "What the suggestions should improve."},
                "limit": {"type": "integer"},
                "max_mana_value": {"type": ["number", "null"]},
            },
            "required": ["deck_id", "goal", "limit", "max_mana_value"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "search_cards",
        "description": "Search local cards by name, oracle text, color identity, and/or maximum mana value.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": ["string", "null"]},
                "text": {"type": ["string", "null"]},
                "color": {"type": ["string", "null"], "description": "One MTG color letter: W, U, B, R, or G."},
                "max_mana_value": {"type": ["number", "null"]},
                "limit": {"type": "integer"},
            },
            "required": ["name", "text", "color", "max_mana_value", "limit"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "search_cards_semantic",
        "description": "Semantic search for local cards by gameplay concept, synergy, or role.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "color": {"type": ["string", "null"], "description": "One MTG color letter: W, U, B, R, or G."},
                "max_mana_value": {"type": ["number", "null"]},
                "limit": {"type": "integer"},
            },
            "required": ["query", "color", "max_mana_value", "limit"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_deck_price",
        "description": "Estimate a deck price from locally refreshed Scryfall price data.",
        "parameters": {
            "type": "object",
            "properties": {
                "deck_id": {"type": "integer"},
                "price": {
                    "type": "string",
                    "enum": ["usd", "usd_foil", "usd_etched", "eur", "eur_foil", "eur_etched", "tix"],
                },
            },
            "required": ["deck_id", "price"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_card_prices",
        "description": "Look up local price data for specific cards by names or IDs.",
        "parameters": {
            "type": "object",
            "properties": {
                "names": {"type": "array", "items": {"type": "string"}},
                "ids": {"type": "array", "items": {"type": "integer"}},
                "limit": {"type": "integer"},
            },
            "required": ["names", "ids", "limit"],
            "additionalProperties": False,
        },
        "strict": False,
    },
]


def execute_chat_tool(db: Session, name: str, args: dict[str, Any]) -> dict[str, Any] | list[dict[str, Any]]:
    if name == "list_decks":
        limit = _limit(args.get("limit"), default=20)
        decks = db.scalars(select(Deck).order_by(Deck.created_at.desc()).limit(limit)).all()
        return [serialize_deck(deck) for deck in decks]

    if name == "get_deck":
        return _deck_with_cards(db, int(args["deck_id"]))

    if name == "analyze_deck":
        deck = get_deck_or_404(db, int(args["deck_id"]))
        rows = get_deck_card_rows(db, deck.id)
        return analyze_deck_data(deck=deck, rows=rows)

    if name == "check_deck_rules":
        deck = get_deck_or_404(db, int(args["deck_id"]))
        rows = get_deck_card_rows(db, deck.id)
        return check_deck_rules_data(deck=deck, rows=rows)

    if name == "diagnose_deck":
        deck = get_deck_or_404(db, int(args["deck_id"]))
        rows = get_deck_card_rows(db, deck.id)
        return diagnose_deck_data(deck=deck, rows=rows)

    if name == "suggest_cards_for_deck":
        deck = get_deck_or_404(db, int(args["deck_id"]))
        rows = get_deck_card_rows(db, deck.id)
        request = DeckSuggestionRequest(
            goal=args.get("goal") or None,
            limit=_limit(args.get("limit"), default=10, maximum=25),
            max_mana_value=args.get("max_mana_value"),
        )
        return suggest_cards_for_deck(deck=deck, rows=rows, request=request, db=db)

    if name == "search_cards":
        limit = _limit(args.get("limit"), default=10)
        stmt = select(Card)
        if args.get("name"):
            stmt = stmt.where(Card.name.ilike(f"%{args['name']}%"))
        if args.get("text"):
            stmt = stmt.where(Card.oracle_text.ilike(f"%{args['text']}%"))
        if args.get("color"):
            stmt = stmt.where(Card.color_identity.contains([str(args["color"]).upper()]))
        if args.get("max_mana_value") is not None:
            stmt = stmt.where(Card.mana_value <= float(args["max_mana_value"]))
        cards = db.scalars(stmt.order_by(Card.name).limit(limit)).all()
        return [serialize_card(card) for card in cards]

    if name == "search_cards_semantic":
        ensure_collection(recreate=False)
        limit = _limit(args.get("limit"), default=10)
        candidate_limit = max(limit * 5, 50)
        points = semantic_search_cards(query=str(args["query"]), limit=candidate_limit)
        card_ids = [int(point.id) for point in points]
        score_by_id = {int(point.id): point.score for point in points}
        stmt = select(Card).where(Card.id.in_(card_ids))
        if args.get("color"):
            stmt = stmt.where(Card.color_identity.contains([str(args["color"]).upper()]))
        if args.get("max_mana_value") is not None:
            stmt = stmt.where(Card.mana_value <= float(args["max_mana_value"]))
        cards = db.scalars(stmt).all()
        card_by_id = {card.id: card for card in cards}
        ranked = [card_by_id[card_id] for card_id in card_ids if card_id in card_by_id][:limit]
        return [{**serialize_card(card), "score": score_by_id.get(card.id)} for card in ranked]

    if name == "get_deck_price":
        return get_deck_price(db, int(args["deck_id"]), price=args.get("price") or "usd")

    if name == "get_card_prices":
        return search_card_prices(
            db,
            names=args.get("names") or [],
            ids=args.get("ids") or [],
            limit=_limit(args.get("limit"), default=25),
        )

    raise ValueError(f"Unknown chat tool: {name}")