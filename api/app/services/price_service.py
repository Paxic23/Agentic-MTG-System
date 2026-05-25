from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import Card, CardPriceRefresh, Deck, DeckCard

SCRYFALL_SOURCE = "scryfall_default_cards"
PRICE_FIELDS = {
    "usd": "price_usd",
    "usd_foil": "price_usd_foil",
    "usd_etched": "price_usd_etched",
    "eur": "price_eur",
    "eur_foil": "price_eur_foil",
    "eur_etched": "price_eur_etched",
    "tix": "price_tix",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _float_or_none(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _normalize_name(name: str) -> str:
    return " ".join(name.lower().replace(" / ", " // ").split())


def _parse_scryfall_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _refresh_row(db: Session) -> CardPriceRefresh:
    row = db.scalar(select(CardPriceRefresh).where(CardPriceRefresh.source == SCRYFALL_SOURCE))
    if row:
        return row
    row = CardPriceRefresh(source=SCRYFALL_SOURCE, status="never")
    db.add(row)
    db.flush()
    return row


def ensure_card_price_schema(db: Session) -> None:
    """Add price columns to existing local DBs.

    SQLAlchemy create_all() creates missing tables but does not alter existing
    tables. This helper keeps old Docker volumes usable until proper Alembic
    migrations are introduced.
    """

    statements = [
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS scryfall_id VARCHAR",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS oracle_id VARCHAR",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS price_usd NUMERIC(12, 2)",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS price_usd_foil NUMERIC(12, 2)",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS price_usd_etched NUMERIC(12, 2)",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS price_eur NUMERIC(12, 2)",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS price_eur_foil NUMERIC(12, 2)",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS price_eur_etched NUMERIC(12, 2)",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS price_tix NUMERIC(12, 2)",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS price_source VARCHAR",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS price_source_updated_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS price_checked_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE cards ADD COLUMN IF NOT EXISTS purchase_uris JSONB",
        "CREATE INDEX IF NOT EXISTS ix_cards_scryfall_id ON cards (scryfall_id)",
        "CREATE INDEX IF NOT EXISTS ix_cards_oracle_id ON cards (oracle_id)",
    ]
    for statement in statements:
        db.execute(text(statement))
    db.commit()


def serialize_card_price(card: Card) -> dict[str, Any]:
    return {
        "card_id": card.id,
        "name": card.name,
        "prices": {
            "usd": _float_or_none(card.price_usd),
            "usd_foil": _float_or_none(card.price_usd_foil),
            "usd_etched": _float_or_none(card.price_usd_etched),
            "eur": _float_or_none(card.price_eur),
            "eur_foil": _float_or_none(card.price_eur_foil),
            "eur_etched": _float_or_none(card.price_eur_etched),
            "tix": _float_or_none(card.price_tix),
        },
        "scryfall_id": card.scryfall_id,
        "oracle_id": card.oracle_id,
        "price_source": card.price_source,
        "price_source_updated_at": card.price_source_updated_at,
        "price_checked_at": card.price_checked_at,
        "purchase_uris": card.purchase_uris,
    }


def get_price_status(db: Session) -> dict[str, Any]:
    row = db.scalar(select(CardPriceRefresh).where(CardPriceRefresh.source == SCRYFALL_SOURCE))
    if not row:
        return {
            "source": SCRYFALL_SOURCE,
            "status": "never",
            "message": "Card prices have not been refreshed yet.",
        }
    return {
        "source": row.source,
        "status": row.status,
        "message": row.message,
        "card_count": row.card_count,
        "matched_card_count": row.matched_card_count,
        "updated_card_count": row.updated_card_count,
        "source_updated_at": row.source_updated_at,
        "last_attempt_at": row.last_attempt_at,
        "last_success_at": row.last_success_at,
    }


def get_card_price(db: Session, card_id: int) -> dict[str, Any]:
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return serialize_card_price(card)


def search_card_prices(
    db: Session,
    *,
    name: str | None = None,
    names: list[str] | None = None,
    ids: list[int] | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    stmt: Select[tuple[Card]] = select(Card)

    if ids:
        stmt = stmt.where(Card.id.in_(ids))
    elif names:
        normalized_names = [_normalize_name(value) for value in names]
        cards = db.scalars(select(Card)).all()
        matched = [card for card in cards if _normalize_name(card.name) in normalized_names]
        return [serialize_card_price(card) for card in matched[:limit]]
    elif name:
        stmt = stmt.where(Card.name.ilike(f"%{name}%"))

    cards = db.scalars(stmt.order_by(Card.name).limit(limit)).all()
    return [serialize_card_price(card) for card in cards]


def get_deck_price(
    db: Session,
    deck_id: int,
    *,
    price: str = "usd",
) -> dict[str, Any]:
    if price not in PRICE_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported price field. Choose one of: {', '.join(sorted(PRICE_FIELDS))}",
        )

    deck = db.get(Deck, deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    price_attr = PRICE_FIELDS[price]
    rows = db.execute(
        select(DeckCard, Card)
        .join(Card, DeckCard.card_id == Card.id)
        .where(DeckCard.deck_id == deck_id)
    ).all()

    total = Decimal("0")
    priced_cards = 0
    missing_price_cards: list[dict[str, Any]] = []
    line_items: list[dict[str, Any]] = []

    for deck_card, card in rows:
        unit_price = getattr(card, price_attr)
        if unit_price is None:
            missing_price_cards.append({"card_id": card.id, "name": card.name, "quantity": deck_card.quantity})
            line_items.append(
                {
                    "card_id": card.id,
                    "name": card.name,
                    "quantity": deck_card.quantity,
                    "unit_price": None,
                    "line_total": None,
                    "is_commander": deck_card.is_commander,
                }
            )
            continue

        priced_cards += deck_card.quantity
        line_total = Decimal(unit_price) * deck_card.quantity
        total += line_total
        line_items.append(
            {
                "card_id": card.id,
                "name": card.name,
                "quantity": deck_card.quantity,
                "unit_price": float(unit_price),
                "line_total": float(line_total),
                "is_commander": deck_card.is_commander,
            }
        )

    return {
        "deck_id": deck.id,
        "deck_name": deck.name,
        "price_field": price,
        "total_estimate": float(total),
        "priced_card_quantity": priced_cards,
        "missing_price_card_quantity": sum(item["quantity"] for item in missing_price_cards),
        "missing_price_cards": missing_price_cards,
        "line_items": sorted(line_items, key=lambda item: item["line_total"] or 0, reverse=True),
        "status": get_price_status(db),
    }


def _get_bulk_download_metadata(settings) -> dict[str, Any]:
    headers = {
        "User-Agent": settings.scryfall_user_agent,
        "Accept": settings.scryfall_accept,
    }
    url = f"https://api.scryfall.com/bulk-data/{settings.scryfall_bulk_type}"
    with httpx.Client(timeout=60) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


def _download_bulk_cards(download_uri: str, settings) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": settings.scryfall_user_agent,
        "Accept": settings.scryfall_accept,
    }
    with httpx.Client(timeout=300) as client:
        response = client.get(download_uri, headers=headers)
        response.raise_for_status()
        return response.json()


def refresh_card_prices(
    db: Session,
    *,
    force: bool = False,
    max_age_days: int | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    max_age = max_age_days or settings.card_price_refresh_interval_days
    row = _refresh_row(db)
    now = _now()

    if not force and row.last_success_at:
        if row.last_success_at > now - timedelta(days=max_age):
            return {
                **get_price_status(db),
                "skipped": True,
                "message": f"Card prices are fresh enough; last successful refresh was less than {max_age} days ago.",
            }

    row.status = "running"
    row.message = "Refreshing card prices from Scryfall bulk data."
    row.last_attempt_at = now
    db.commit()

    try:
        metadata = _get_bulk_download_metadata(settings)
        download_uri = metadata.get("download_uri")
        if not download_uri:
            raise RuntimeError("Scryfall bulk metadata did not include download_uri.")

        source_updated_at = _parse_scryfall_datetime(metadata.get("updated_at"))
        bulk_cards = _download_bulk_cards(download_uri, settings)
        scryfall_by_name = {
            _normalize_name(card["name"]): card
            for card in bulk_cards
            if isinstance(card, dict) and card.get("name")
        }

        matched = 0
        updated = 0
        checked_at = _now()
        local_cards = db.scalars(select(Card)).all()

        for local_card in local_cards:
            scryfall_card = scryfall_by_name.get(_normalize_name(local_card.name))
            if not scryfall_card:
                continue

            matched += 1
            prices = scryfall_card.get("prices") or {}
            local_card.scryfall_id = scryfall_card.get("id")
            local_card.oracle_id = scryfall_card.get("oracle_id")
            local_card.price_usd = _decimal_or_none(prices.get("usd"))
            local_card.price_usd_foil = _decimal_or_none(prices.get("usd_foil"))
            local_card.price_usd_etched = _decimal_or_none(prices.get("usd_etched"))
            local_card.price_eur = _decimal_or_none(prices.get("eur"))
            local_card.price_eur_foil = _decimal_or_none(prices.get("eur_foil"))
            local_card.price_eur_etched = _decimal_or_none(prices.get("eur_etched"))
            local_card.price_tix = _decimal_or_none(prices.get("tix"))
            local_card.price_source = SCRYFALL_SOURCE
            local_card.price_source_updated_at = source_updated_at
            local_card.price_checked_at = checked_at
            local_card.purchase_uris = scryfall_card.get("purchase_uris")
            updated += 1

        row.status = "success"
        row.message = "Card prices refreshed successfully."
        row.card_count = len(bulk_cards)
        row.matched_card_count = matched
        row.updated_card_count = updated
        row.source_updated_at = source_updated_at
        row.last_success_at = checked_at
        db.commit()

        return {
            **get_price_status(db),
            "skipped": False,
        }
    except Exception as exc:
        db.rollback()
        row = _refresh_row(db)
        row.status = "failed"
        row.message = f"{exc.__class__.__name__}: {exc}"
        row.last_attempt_at = _now()
        db.commit()
        return {
            **get_price_status(db),
            "skipped": False,
        }


def maybe_refresh_card_prices_on_startup() -> None:
    settings = get_settings()
    if not settings.card_price_auto_refresh_on_startup:
        return

    def runner() -> None:
        db = SessionLocal()
        try:
            ensure_card_price_schema(db)
            refresh_card_prices(
                db,
                force=False,
                max_age_days=settings.card_price_refresh_interval_days,
            )
        finally:
            db.close()

    if settings.card_price_startup_refresh_background:
        thread = threading.Thread(target=runner, name="card-price-refresh", daemon=True)
        thread.start()
    else:
        runner()
