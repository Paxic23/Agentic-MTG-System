from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    mana_cost: Mapped[str | None] = mapped_column(String, nullable=True)
    mana_value: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    type_line: Mapped[str | None] = mapped_column(String, nullable=True)
    oracle_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    colors: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    color_identity: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    # Price data is refreshed from Scryfall bulk data and stored locally so the
    # app does not need to call external APIs every time a card/deck is viewed.
    scryfall_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    oracle_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    price_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_usd_foil: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_usd_etched: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_eur: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_eur_foil: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_eur_etched: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_tix: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_source: Mapped[str | None] = mapped_column(String, nullable=True)
    price_source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    price_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purchase_uris: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    deck_entries: Mapped[list["DeckCard"]] = relationship(back_populates="card")


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    format: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    cards: Mapped[list["DeckCard"]] = relationship(
        back_populates="deck",
        cascade="all, delete-orphan",
    )


class DeckCard(Base):
    __tablename__ = "deck_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id"), index=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    is_commander: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )

    deck: Mapped[Deck] = relationship(back_populates="cards")
    card: Mapped[Card] = relationship(back_populates="deck_entries")

    __table_args__ = (
        UniqueConstraint("deck_id", "card_id", name="uq_deck_card"),
    )


class CardPriceRefresh(Base):
    __tablename__ = "card_price_refreshes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String, unique=True, index=True)
    status: Mapped[str] = mapped_column(String, default="never")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    card_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matched_card_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_card_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
