from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Card
from app.schemas import SemanticSearchRequest
from app.services.deck_service import serialize_card
from app.vector import ensure_collection, semantic_search_cards


router = APIRouter(tags=["cards"])


@router.get("/cards")
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

    return [serialize_card(card) for card in cards]


@router.get("/cards/{card_id}")
def get_card(card_id: int, db: Session = Depends(get_db)):
    card = db.get(Card, card_id)

    if not card:
        return {"error": "Card not found"}

    return serialize_card(card)


@router.post("/cards/semantic-search")
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
            **serialize_card(card),
            "score": score_by_id.get(card.id),
        }
        for card in ranked_cards
    ]
