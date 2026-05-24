from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import Base, engine, get_db
from app.models import Card

app = FastAPI(title="MTG Deck Lab API")

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