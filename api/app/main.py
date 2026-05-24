from collections import Counter, defaultdict
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from app.vector import ensure_collection, semantic_search_cards

from app.db import Base, engine, get_db
from app.models import Card, Deck, DeckCard

app = FastAPI(title="MTG Deck Lab API")

class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 10
    color: str | None = None
    max_mana_value: float | None = None


class CreateDeckRequest(BaseModel):
    name: str
    format: str | None = None
    description: str | None = None


class AddCardToDeckRequest(BaseModel):
    card_id: int
    quantity: int = 1


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cards")
def search_cards(
    name: str | None = None,
    text: str | None = None,
    max_mana_value: float | None = None,
    color: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
):
    stmt = select(Card)

    if name:
        stmt = stmt.where(Card.name.ilike(f"%{name}%"))

    if text:
        stmt = stmt.where(Card.oracle_text.ilike(f"%{text}%"))

    if max_mana_value is not None:
        stmt = stmt.where(Card.mana_value <= max_mana_value)

    if color:
        stmt = stmt.where(Card.color_identity.contains([color.upper()]))

    stmt = stmt.order_by(Card.name).limit(limit)

    cards = db.scalars(stmt).all()

    return [
        {
            "id": card.id,
            "name": card.name,
            "mana_cost": card.mana_cost,
            "mana_value": card.mana_value,
            "type_line": card.type_line,
            "oracle_text": card.oracle_text,
            "colors": card.colors,
            "color_identity": card.color_identity,
            "keywords": card.keywords,
        }
        for card in cards
    ]

def serialize_card(card: Card):
    return {
        "id": card.id,
        "name": card.name,
        "mana_cost": card.mana_cost,
        "mana_value": card.mana_value,
        "type_line": card.type_line,
        "oracle_text": card.oracle_text,
        "colors": card.colors,
        "color_identity": card.color_identity,
        "keywords": card.keywords,
    }


def serialize_deck(deck: Deck):
    return {
        "id": deck.id,
        "name": deck.name,
        "format": deck.format,
        "description": deck.description,
        "created_at": deck.created_at,
    }


def classify_card_type(type_line: str | None) -> str:
    if not type_line:
        return "Unknown"

    type_order = [
        "Creature",
        "Land",
        "Instant",
        "Sorcery",
        "Artifact",
        "Enchantment",
        "Planeswalker",
        "Battle",
    ]

    for card_type in type_order:
        if card_type in type_line:
            return card_type

    return "Other"

@app.get("/cards/{card_id}")
def get_card(card_id: int, db: Session = Depends(get_db)):
    card = db.get(Card, card_id)

    if not card:
        return {"error": "Card not found"}

    return {
        "id": card.id,
        "name": card.name,
        "mana_cost": card.mana_cost,
        "mana_value": card.mana_value,
        "type_line": card.type_line,
        "oracle_text": card.oracle_text,
        "colors": card.colors,
        "color_identity": card.color_identity,
        "keywords": card.keywords,
    }

@app.post("/cards/semantic-search")
def semantic_search(
    request: SemanticSearchRequest,
    db: Session = Depends(get_db),
):
    ensure_collection(recreate=False)

    candidate_limit = max(request.limit * 5, 50)

    qdrant_results = semantic_search_cards(
        query=request.query,
        limit=candidate_limit,
    )

    card_ids = [int(point.id) for point in qdrant_results]
    score_by_id = {int(point.id): point.score for point in qdrant_results}

    stmt = select(Card).where(Card.id.in_(card_ids))

    if request.color:
        stmt = stmt.where(Card.color_identity.contains([request.color.upper()]))

    if request.max_mana_value is not None:
        stmt = stmt.where(Card.mana_value <= request.max_mana_value)

    cards = db.scalars(stmt).all()

    card_by_id = {card.id: card for card in cards}

    ranked_cards = [
        card_by_id[card_id]
        for card_id in card_ids
        if card_id in card_by_id
    ][: request.limit]

    return [
        {
            "id": card.id,
            "score": score_by_id.get(card.id),
            "name": card.name,
            "mana_cost": card.mana_cost,
            "mana_value": card.mana_value,
            "type_line": card.type_line,
            "oracle_text": card.oracle_text,
            "colors": card.colors,
            "color_identity": card.color_identity,
            "keywords": card.keywords,
        }
        for card in ranked_cards
    ]

@app.post("/decks")
def create_deck(
    request: CreateDeckRequest,
    db: Session = Depends(get_db),
):
    deck = Deck(
        name=request.name,
        format=request.format,
        description=request.description,
    )

    db.add(deck)
    db.commit()
    db.refresh(deck)

    return serialize_deck(deck)


@app.get("/decks")
def list_decks(db: Session = Depends(get_db)):
    decks = db.scalars(select(Deck).order_by(Deck.created_at.desc())).all()
    return [serialize_deck(deck) for deck in decks]


@app.get("/decks/{deck_id}")
def get_deck(
    deck_id: int,
    db: Session = Depends(get_db),
):
    deck = db.get(Deck, deck_id)

    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    rows = db.execute(
        select(DeckCard, Card)
        .join(Card, DeckCard.card_id == Card.id)
        .where(DeckCard.deck_id == deck_id)
        .order_by(Card.name)
    ).all()

    return {
        **serialize_deck(deck),
        "cards": [
            {
                "quantity": deck_card.quantity,
                "card": serialize_card(card),
            }
            for deck_card, card in rows
        ],
    }


@app.post("/decks/{deck_id}/cards")
def add_card_to_deck(
    deck_id: int,
    request: AddCardToDeckRequest,
    db: Session = Depends(get_db),
):
    deck = db.get(Deck, deck_id)

    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    card = db.get(Card, request.card_id)

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if request.quantity < 1:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")

    existing = db.scalar(
        select(DeckCard).where(
            DeckCard.deck_id == deck_id,
            DeckCard.card_id == request.card_id,
        )
    )

    if existing:
        existing.quantity += request.quantity
        deck_card = existing
    else:
        deck_card = DeckCard(
            deck_id=deck_id,
            card_id=request.card_id,
            quantity=request.quantity,
        )
        db.add(deck_card)

    db.commit()
    db.refresh(deck_card)

    return {
        "deck_id": deck_id,
        "quantity": deck_card.quantity,
        "card": serialize_card(card),
    }


@app.delete("/decks/{deck_id}/cards/{card_id}")
def remove_card_from_deck(
    deck_id: int,
    card_id: int,
    db: Session = Depends(get_db),
):
    deck_card = db.scalar(
        select(DeckCard).where(
            DeckCard.deck_id == deck_id,
            DeckCard.card_id == card_id,
        )
    )

    if not deck_card:
        raise HTTPException(status_code=404, detail="Card not found in deck")

    db.delete(deck_card)
    db.commit()

    return {"status": "removed"}


@app.get("/decks/{deck_id}/analysis")
def analyze_deck(
    deck_id: int,
    db: Session = Depends(get_db),
):
    deck = db.get(Deck, deck_id)

    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    rows = db.execute(
        select(DeckCard, Card)
        .join(Card, DeckCard.card_id == Card.id)
        .where(DeckCard.deck_id == deck_id)
    ).all()

    total_cards = 0
    nonland_cards = 0

    mana_curve = defaultdict(int)
    type_counts = Counter()
    color_identity_counts = Counter()

    for deck_card, card in rows:
        quantity = deck_card.quantity
        total_cards += quantity

        primary_type = classify_card_type(card.type_line)
        type_counts[primary_type] += quantity

        for color in card.color_identity or []:
            color_identity_counts[color] += quantity

        is_land = card.type_line and "Land" in card.type_line

        if not is_land:
            nonland_cards += quantity

            mana_value = int(card.mana_value or 0)
            bucket = "7+" if mana_value >= 7 else str(mana_value)
            mana_curve[bucket] += quantity

    average_mana_value = None

    if nonland_cards > 0:
        weighted_mana_total = 0

        for deck_card, card in rows:
            is_land = card.type_line and "Land" in card.type_line

            if is_land:
                continue

            weighted_mana_total += (card.mana_value or 0) * deck_card.quantity

        average_mana_value = round(weighted_mana_total / nonland_cards, 2)

    return {
        "deck": serialize_deck(deck),
        "summary": {
            "total_cards": total_cards,
            "nonland_cards": nonland_cards,
            "land_cards": type_counts.get("Land", 0),
            "average_mana_value": average_mana_value,
        },
        "mana_curve": dict(sorted(mana_curve.items(), key=lambda item: item[0])),
        "type_counts": dict(type_counts),
        "color_identity_counts": dict(color_identity_counts),
    }