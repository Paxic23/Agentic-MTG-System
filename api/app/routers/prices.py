from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import CardPriceSearchRequest
from app.services.price_service import (
    get_card_price,
    get_deck_price,
    get_price_status,
    refresh_card_prices,
    search_card_prices,
)

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/status")
def card_price_status(db: Session = Depends(get_db)):
    return get_price_status(db)


@router.post("/refresh")
def refresh_prices(
    force: bool = False,
    db: Session = Depends(get_db),
):
    return refresh_card_prices(db, force=force)


@router.get("/cards/{card_id}")
def read_card_price(card_id: int, db: Session = Depends(get_db)):
    return get_card_price(db, card_id)


@router.get("/cards")
def read_card_prices(
    name: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
):
    return search_card_prices(db, name=name, limit=limit)


@router.post("/cards/search")
def search_prices(
    request: CardPriceSearchRequest,
    db: Session = Depends(get_db),
):
    return search_card_prices(db, names=request.names, ids=request.ids, limit=max(len(request.names), len(request.ids), 25))


@router.get("/decks/{deck_id}")
def read_deck_price(
    deck_id: int,
    price: str = "usd",
    db: Session = Depends(get_db),
):
    return get_deck_price(db, deck_id, price=price)
