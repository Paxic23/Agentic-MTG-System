from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Card, Deck, DeckCard
from app.schemas import (
    AddCardToDeckRequest,
    CreateDeckRequest,
    DeckSuggestionRequest,
    ImportDecklistRequest,
)
from app.services.deck_service import (
    add_or_increment_deck_card,
    analyze_deck_data,
    check_deck_rules_data,
    diagnose_deck_data,
    find_card_for_import,
    get_deck_card_rows,
    get_deck_or_404,
    is_probably_moxfield_decklist,
    parse_decklist_line,
    serialize_card,
    serialize_deck,
    suggest_cards_for_deck,
)


router = APIRouter(tags=["decks"])


@router.post("/decks")
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


@router.get("/decks")
def list_decks(db: Session = Depends(get_db)):
    decks = db.scalars(select(Deck).order_by(Deck.created_at.desc())).all()
    return [serialize_deck(deck) for deck in decks]


@router.get("/decks/{deck_id}")
def get_deck(
    deck_id: int,
    db: Session = Depends(get_db),
):
    deck = get_deck_or_404(db, deck_id)

    rows = (
        db.execute(
            select(DeckCard, Card)
            .join(Card, DeckCard.card_id == Card.id)
            .where(DeckCard.deck_id == deck_id)
            .order_by(Card.name)
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


@router.post("/decks/{deck_id}/cards")
def add_card_to_deck(
    deck_id: int,
    request: AddCardToDeckRequest,
    db: Session = Depends(get_db),
):
    get_deck_or_404(db, deck_id)

    card = db.get(Card, request.card_id)

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if request.quantity < 1:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")

    deck_card = add_or_increment_deck_card(
        db=db,
        deck_id=deck_id,
        card_id=request.card_id,
        quantity=request.quantity,
    )

    db.commit()
    db.refresh(deck_card)

    return {
        "deck_id": deck_id,
        "quantity": deck_card.quantity,
        "card": serialize_card(card),
    }


@router.delete("/decks/{deck_id}/cards/{card_id}")
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


@router.get("/decks/{deck_id}/analysis")
def analyze_deck(
    deck_id: int,
    db: Session = Depends(get_db),
):
    deck = get_deck_or_404(db, deck_id)
    rows = get_deck_card_rows(db, deck_id)

    return analyze_deck_data(deck=deck, rows=rows)


@router.post("/decks/{deck_id}/suggestions")
def suggest_deck_cards(
    deck_id: int,
    request: DeckSuggestionRequest,
    db: Session = Depends(get_db),
):
    deck = get_deck_or_404(db, deck_id)
    rows = get_deck_card_rows(db, deck_id)

    return suggest_cards_for_deck(deck=deck, rows=rows, request=request, db=db)


@router.post("/decks/{deck_id}/import")
def import_decklist(
    deck_id: int,
    request: ImportDecklistRequest,
    db: Session = Depends(get_db),
):
    deck = get_deck_or_404(db, deck_id)

    if request.replace_existing:
        existing_rows = db.scalars(
            select(DeckCard).where(DeckCard.deck_id == deck_id)
        ).all()

        for row in existing_rows:
            db.delete(row)

        db.flush()

    imported = []
    unmatched = []
    skipped = []
    should_assign_moxfield_commander = (
        (deck.format or "").lower() == "commander"
        and is_probably_moxfield_decklist(request.decklist)
    )
    commander_candidate_card_id: int | None = None
    first_parsed_seen = False

    for raw_line in request.decklist.splitlines():
        parsed = parse_decklist_line(raw_line)

        if parsed is None:
            skipped.append(raw_line)
            continue

        quantity, card_name = parsed

        card = find_card_for_import(db, card_name)

        if not first_parsed_seen:
            first_parsed_seen = True
            if card:
                commander_candidate_card_id = card.id

        if not card:
            unmatched.append(
                {
                    "line": raw_line,
                    "parsed_name": card_name,
                    "quantity": quantity,
                }
            )
            continue

        add_or_increment_deck_card(
            db=db,
            deck_id=deck_id,
            card_id=card.id,
            quantity=quantity,
        )

        imported.append(
            {
                "quantity": quantity,
                "card": serialize_card(card),
            }
        )

    if should_assign_moxfield_commander and commander_candidate_card_id is not None:
        # Session uses autoflush=False, so flush imported rows before selecting.
        db.flush()

        existing_rows = db.scalars(
            select(DeckCard).where(DeckCard.deck_id == deck_id)
        ).all()

        for row in existing_rows:
            row.is_commander = False

        commander_row = db.scalar(
            select(DeckCard).where(
                DeckCard.deck_id == deck_id,
                DeckCard.card_id == commander_candidate_card_id,
            )
        )

        if commander_row:
            commander_row.is_commander = True
            commander_row.quantity = 1

    db.commit()

    return {
        "deck_id": deck_id,
        "imported_count": len(imported),
        "unmatched_count": len(unmatched),
        "skipped_count": len(skipped),
        "imported": imported,
        "unmatched": unmatched,
        "skipped": skipped,
    }


@router.get("/decks/{deck_id}/export")
def export_decklist(
    deck_id: int,
    db: Session = Depends(get_db),
):
    deck = get_deck_or_404(db, deck_id)

    rows = (
        db.execute(
            select(DeckCard, Card)
            .join(Card, DeckCard.card_id == Card.id)
            .where(DeckCard.deck_id == deck_id)
            .order_by(Card.name)
        )
        .all()
    )

    lines = [
        f"{deck_card.quantity} {card.name}"
        for deck_card, card in rows
    ]

    return {
        "deck": serialize_deck(deck),
        "decklist": "\n".join(lines),
    }


@router.patch("/decks/{deck_id}/cards/{card_id}/commander")
def set_deck_commander(
    deck_id: int,
    card_id: int,
    db: Session = Depends(get_db),
):
    deck = get_deck_or_404(db, deck_id)

    if (deck.format or "").lower() != "commander":
        raise HTTPException(
            status_code=400,
            detail="Only Commander decks can have a commander",
        )

    deck_card = db.scalar(
        select(DeckCard).where(
            DeckCard.deck_id == deck_id,
            DeckCard.card_id == card_id,
        )
    )

    if not deck_card:
        raise HTTPException(status_code=404, detail="Card not found in deck")

    existing_rows = db.scalars(
        select(DeckCard).where(DeckCard.deck_id == deck_id)
    ).all()

    for row in existing_rows:
        row.is_commander = False

    deck_card.is_commander = True
    deck_card.quantity = 1

    db.commit()
    db.refresh(deck_card)

    card = db.get(Card, card_id)

    return {
        "deck_id": deck_id,
        "is_commander": deck_card.is_commander,
        "quantity": deck_card.quantity,
        "card": serialize_card(card),
    }


@router.delete("/decks/{deck_id}/commander")
def clear_deck_commander(
    deck_id: int,
    db: Session = Depends(get_db),
):
    get_deck_or_404(db, deck_id)

    existing_rows = db.scalars(
        select(DeckCard).where(DeckCard.deck_id == deck_id)
    ).all()

    for row in existing_rows:
        row.is_commander = False

    db.commit()

    return {"status": "commander cleared"}


@router.get("/decks/{deck_id}/rules-check")
def check_deck_rules(
    deck_id: int,
    db: Session = Depends(get_db),
):
    deck = get_deck_or_404(db, deck_id)
    rows = get_deck_card_rows(db, deck_id)

    return check_deck_rules_data(deck=deck, rows=rows)


@router.get("/decks/{deck_id}/diagnosis")
def diagnose_deck(
    deck_id: int,
    db: Session = Depends(get_db),
):
    deck = get_deck_or_404(db, deck_id)
    rows = get_deck_card_rows(db, deck_id)

    return diagnose_deck_data(deck=deck, rows=rows)
