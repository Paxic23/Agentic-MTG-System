import re
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

class DeckSuggestionRequest(BaseModel):
    goal: str | None = None
    limit: int = 10
    max_mana_value: float | None = None
    color_identity: list[str] | None = None

class ImportDecklistRequest(BaseModel):
    decklist: str
    replace_existing: bool = False


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

BASIC_LAND_NAMES = {
    "Plains",
    "Island",
    "Swamp",
    "Mountain",
    "Forest",
    "Wastes",
}


def is_basic_land(card: Card) -> bool:
    type_line = card.type_line or ""

    return (
        card.name in BASIC_LAND_NAMES
        or ("Basic" in type_line and "Land" in type_line)
    )


def is_commander_legalish(card: Card) -> bool:
    type_line = card.type_line or ""
    oracle_text = card.oracle_text or ""

    is_legendary_creature = "Legendary" in type_line and "Creature" in type_line
    says_can_be_commander = "can be your commander" in oracle_text.lower()

    return is_legendary_creature or says_can_be_commander


def infer_card_roles(card: Card) -> list[str]:
    roles = set()

    text = (card.oracle_text or "").lower()
    type_line = (card.type_line or "").lower()

    if "land" in type_line:
        roles.add("land")

    if "creature" in type_line:
        roles.add("creature")

    if "instant" in type_line or "sorcery" in type_line:
        roles.add("spell")

    if (
        "draw a card" in text
        or "draw two cards" in text
        or "draw cards" in text
        or "you draw" in text
    ):
        roles.add("card draw")

    if (
        "add " in text and "mana" in text
        or "search your library" in text and "land" in text
    ):
        roles.add("ramp / fixing")

    if (
        "destroy target" in text
        or "exile target" in text
        or "return target" in text
        or "damage to target" in text
    ):
        roles.add("removal")

    if (
        "destroy all" in text
        or "exile all" in text
        or "destroy each" in text
        or "each creature" in text and "destroy" in text
    ):
        roles.add("board wipe")

    if "counter target" in text:
        roles.add("interaction")

    if (
        "return target" in text and "graveyard" in text
        or "return" in text and "from your graveyard" in text
        or "put target creature card from your graveyard" in text
    ):
        roles.add("recursion")

    if "graveyard" in text:
        roles.add("graveyard synergy")

    if "sacrifice" in text:
        roles.add("sacrifice synergy")

    if "sacrifice" in text and (":" in text or "you may sacrifice" in text):
        roles.add("sacrifice outlet")

    if (
        "whenever" in text
        and (
            "dies" in text
            or "is put into a graveyard" in text
            or "creature is put into a graveyard" in text
        )
    ):
        roles.add("death trigger")

    if "create" in text and "token" in text:
        roles.add("token maker")

    if (
        "indestructible" in text
        or "hexproof" in text
        or "protection from" in text
        or "phase out" in text
    ):
        roles.add("protection")

    if (
        "each opponent loses" in text
        or "opponent loses" in text
        or "you win the game" in text
        or "loses the game" in text
    ):
        roles.add("win condition")

    return sorted(roles)


def get_deck_card_rows(db: Session, deck_id: int):
    return db.execute(
        select(DeckCard, Card)
        .join(Card, DeckCard.card_id == Card.id)
        .where(DeckCard.deck_id == deck_id)
    ).all()


def get_commander_entry(rows):
    for deck_card, card in rows:
        if deck_card.is_commander:
            return deck_card, card

    return None

def card_color_identity_is_allowed(
    card: Card,
    allowed_colors: set[str] | None,
) -> bool:
    if allowed_colors is None:
        return True

    card_colors = set(card.color_identity or [])

    return card_colors.issubset(allowed_colors)


def build_deck_recommendation_query(
    deck: Deck,
    rows: list[tuple[DeckCard, Card]],
    goal: str | None,
) -> str:
    type_counts = Counter()
    keyword_counts = Counter()
    oracle_examples: list[str] = []
    card_names: list[str] = []
    deck_colors = set()

    for deck_card, card in rows:
        quantity = deck_card.quantity

        type_counts[classify_card_type(card.type_line)] += quantity

        for keyword in card.keywords or []:
            keyword_counts[keyword] += quantity

        for color in card.color_identity or []:
            deck_colors.add(color)

        if len(card_names) < 20:
            card_names.append(card.name)

        if card.oracle_text and len(oracle_examples) < 12:
            oracle_examples.append(card.oracle_text)

    top_types = ", ".join(
        card_type for card_type, _ in type_counts.most_common(5)
    )

    top_keywords = ", ".join(
        keyword for keyword, _ in keyword_counts.most_common(8)
    )

    colors_text = ", ".join(sorted(deck_colors)) or "unknown"

    goal_text = goal or "cards that synergize with the existing deck themes"

    oracle_text = "\n".join(oracle_examples)

    existing_cards_text = ", ".join(card_names)

    return f"""
Magic: The Gathering card recommendations.

Deck name: {deck.name}
Deck format: {deck.format or "unknown"}
Deck colors: {colors_text}

User goal:
{goal_text}

Current deck card examples:
{existing_cards_text}

Current deck type themes:
{top_types}

Current deck keyword themes:
{top_keywords}

Current deck oracle text examples:
{oracle_text}

Suggest cards that support the deck's strategy, improve synergy, and fit the stated goal.
""".strip()

def serialize_deck(deck: Deck):
    return {
        "id": deck.id,
        "name": deck.name,
        "format": deck.format,
        "description": deck.description,
        "created_at": deck.created_at,
    }

def parse_decklist_line(line: str) -> tuple[int, str] | None:
    clean_line = line.strip()

    if not clean_line:
        return None

    if clean_line.startswith("#"):
        return None

    section_headers = {
        "deck",
        "commander",
        "sideboard",
        "maybeboard",
        "companion",
        "mainboard",
    }

    if clean_line.lower().rstrip(":") in section_headers:
        return None

    # Supports MTGA-style lines like:
    # 1 Blood Artist (JMP) 206
    clean_line = re.sub(
        r"\s+\([A-Z0-9]{2,8}\)\s+\d+.*$",
        "",
        clean_line,
    )

    # Supports lines like:
    # 1 Blood Artist [JMP]
    clean_line = re.sub(
        r"\s+\[[A-Z0-9]{2,8}\].*$",
        "",
        clean_line,
    )

    # Supports:
    # 1 Blood Artist
    # 1x Blood Artist
    match = re.match(
        r"^(?P<quantity>\d+)\s*x?\s+(?P<name>.+)$",
        clean_line,
        flags=re.IGNORECASE,
    )

    if match:
        quantity = int(match.group("quantity"))
        name = match.group("name").strip()
    else:
        quantity = 1
        name = clean_line.strip()

    if quantity < 1 or not name:
        return None

    return quantity, name


def add_or_increment_deck_card(
    db: Session,
    deck_id: int,
    card_id: int,
    quantity: int,
) -> DeckCard:
    existing = db.scalar(
        select(DeckCard).where(
            DeckCard.deck_id == deck_id,
            DeckCard.card_id == card_id,
        )
    )

    if existing:
        existing.quantity += quantity
        return existing

    deck_card = DeckCard(
        deck_id=deck_id,
        card_id=card_id,
        quantity=quantity,
    )

    db.add(deck_card)

    return deck_card

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
            "is_commander": deck_card.is_commander,
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


@app.post("/decks/{deck_id}/import")
def import_decklist(
    deck_id: int,
    request: ImportDecklistRequest,
    db: Session = Depends(get_db),
):
    deck = db.get(Deck, deck_id)

    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

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

    for raw_line in request.decklist.splitlines():
        parsed = parse_decklist_line(raw_line)

        if parsed is None:
            skipped.append(raw_line)
            continue

        quantity, card_name = parsed

        card = db.scalar(
            select(Card).where(Card.name.ilike(card_name))
        )

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


@app.get("/decks/{deck_id}/export")
def export_decklist(
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

    lines = [
        f"{deck_card.quantity} {card.name}"
        for deck_card, card in rows
    ]

    return {
        "deck": serialize_deck(deck),
        "decklist": "\n".join(lines),
    }


@app.patch("/decks/{deck_id}/cards/{card_id}/commander")
def set_deck_commander(
    deck_id: int,
    card_id: int,
    db: Session = Depends(get_db),
):
    deck = db.get(Deck, deck_id)

    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

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


@app.delete("/decks/{deck_id}/commander")
def clear_deck_commander(
    deck_id: int,
    db: Session = Depends(get_db),
):
    deck = db.get(Deck, deck_id)

    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    existing_rows = db.scalars(
        select(DeckCard).where(DeckCard.deck_id == deck_id)
    ).all()

    for row in existing_rows:
        row.is_commander = False

    db.commit()

    return {"status": "commander cleared"}

@app.get("/decks/{deck_id}/rules-check")
def check_deck_rules(
    deck_id: int,
    db: Session = Depends(get_db),
):
    deck = db.get(Deck, deck_id)

    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    rows = get_deck_card_rows(db, deck_id)

    issues = []

    total_cards = sum(deck_card.quantity for deck_card, _ in rows)
    deck_format = (deck.format or "").lower()

    if deck_format == "commander":
        commander_entry = get_commander_entry(rows)

        if total_cards != 100:
            issues.append(
                {
                    "severity": "error",
                    "code": "commander_deck_size",
                    "message": f"Commander decks should contain exactly 100 cards. This deck has {total_cards}.",
                }
            )

        if not commander_entry:
            issues.append(
                {
                    "severity": "error",
                    "code": "missing_commander",
                    "message": "Commander deck has no commander selected.",
                }
            )
        else:
            commander_deck_card, commander_card = commander_entry

            if commander_deck_card.quantity != 1:
                issues.append(
                    {
                        "severity": "error",
                        "code": "commander_quantity",
                        "message": "The commander should have quantity 1.",
                    }
                )

            if not is_commander_legalish(commander_card):
                issues.append(
                    {
                        "severity": "warning",
                        "code": "commander_legality_unverified",
                        "message": f"{commander_card.name} does not look like a normal legal commander. This checker only supports a simple legendary-creature / 'can be your commander' rule.",
                    }
                )

            allowed_colors = set(commander_card.color_identity or [])

            for deck_card, card in rows:
                if deck_card.is_commander:
                    continue

                card_colors = set(card.color_identity or [])

                if not card_colors.issubset(allowed_colors):
                    issues.append(
                        {
                            "severity": "error",
                            "code": "color_identity_violation",
                            "message": f"{card.name} has color identity {sorted(card_colors)}, which is outside the commander's color identity {sorted(allowed_colors)}.",
                        }
                    )

        for deck_card, card in rows:
            if deck_card.is_commander:
                continue

            if is_basic_land(card):
                continue

            if deck_card.quantity > 1:
                issues.append(
                    {
                        "severity": "error",
                        "code": "commander_singleton_violation",
                        "message": f"{card.name} appears {deck_card.quantity} times. Commander is singleton except for basic lands.",
                    }
                )

    is_valid = not any(issue["severity"] == "error" for issue in issues)

    return {
        "deck": serialize_deck(deck),
        "format": deck.format,
        "is_valid": is_valid,
        "total_cards": total_cards,
        "issues": issues,
    }


@app.get("/decks/{deck_id}/diagnosis")
def diagnose_deck(
    deck_id: int,
    db: Session = Depends(get_db),
):
    deck = db.get(Deck, deck_id)

    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    rows = get_deck_card_rows(db, deck_id)

    total_cards = 0
    land_cards = 0
    nonland_cards = 0
    weighted_mana_total = 0.0

    role_counts = Counter()
    type_counts = Counter()
    color_counts = Counter()

    for deck_card, card in rows:
        quantity = deck_card.quantity
        total_cards += quantity

        primary_type = classify_card_type(card.type_line)
        type_counts[primary_type] += quantity

        for color in card.color_identity or []:
            color_counts[color] += quantity

        roles = infer_card_roles(card)

        for role in roles:
            role_counts[role] += quantity

        is_land_card = "land" in (card.type_line or "").lower()

        if is_land_card:
            land_cards += quantity
        else:
            nonland_cards += quantity
            weighted_mana_total += (card.mana_value or 0) * quantity

    average_mana_value = None

    if nonland_cards > 0:
        average_mana_value = round(weighted_mana_total / nonland_cards, 2)

    findings = []

    deck_format = (deck.format or "").lower()
    commander_entry = get_commander_entry(rows)

    if deck_format == "commander":
        if total_cards < 100:
            findings.append(
                {
                    "severity": "warning",
                    "category": "deck size",
                    "message": f"This Commander deck has {total_cards}/100 cards. It needs {100 - total_cards} more cards.",
                    "suggested_goal": "cards that fit the deck's main strategy and color identity",
                }
            )
        elif total_cards > 100:
            findings.append(
                {
                    "severity": "error",
                    "category": "deck size",
                    "message": f"This Commander deck has {total_cards}/100 cards. It needs {total_cards - 100} cuts.",
                    "suggested_goal": "identify weak or redundant cards to cut",
                }
            )
        else:
            findings.append(
                {
                    "severity": "ok",
                    "category": "deck size",
                    "message": "This Commander deck has exactly 100 cards.",
                    "suggested_goal": None,
                }
            )

        if not commander_entry:
            findings.append(
                {
                    "severity": "warning",
                    "category": "commander",
                    "message": "No commander is selected yet.",
                    "suggested_goal": "legendary creatures that could lead this deck",
                }
            )

        if land_cards < 34:
            findings.append(
                {
                    "severity": "warning",
                    "category": "mana base",
                    "message": f"This deck has {land_cards} lands. Many Commander decks want roughly 35–38 lands, depending on ramp and curve.",
                    "suggested_goal": "lands and mana fixing for this deck",
                }
            )
        elif land_cards > 42:
            findings.append(
                {
                    "severity": "warning",
                    "category": "mana base",
                    "message": f"This deck has {land_cards} lands, which may be high unless the strategy specifically wants many lands.",
                    "suggested_goal": "nonland payoff cards that fit this deck",
                }
            )
        else:
            findings.append(
                {
                    "severity": "ok",
                    "category": "mana base",
                    "message": f"This deck has {land_cards} lands, which is within a typical Commander range.",
                    "suggested_goal": None,
                }
            )

        if role_counts["ramp / fixing"] < 8:
            findings.append(
                {
                    "severity": "warning",
                    "category": "ramp",
                    "message": f"This deck appears to have {role_counts['ramp / fixing']} ramp/fixing cards. Many Commander decks want around 8–12.",
                    "suggested_goal": "mana ramp and color fixing that fits this deck",
                }
            )

        if role_counts["card draw"] < 8:
            findings.append(
                {
                    "severity": "warning",
                    "category": "card draw",
                    "message": f"This deck appears to have {role_counts['card draw']} card-draw cards. Many Commander decks want around 8–12.",
                    "suggested_goal": "card draw engines and efficient draw spells for this deck",
                }
            )

        if role_counts["removal"] < 6:
            findings.append(
                {
                    "severity": "warning",
                    "category": "interaction",
                    "message": f"This deck appears to have {role_counts['removal']} targeted removal cards. It may need more interaction.",
                    "suggested_goal": "targeted removal that fits this deck",
                }
            )

        if role_counts["board wipe"] < 2:
            findings.append(
                {
                    "severity": "info",
                    "category": "board wipes",
                    "message": f"This deck appears to have {role_counts['board wipe']} board wipes. Many Commander decks want around 2–4.",
                    "suggested_goal": "board wipes that fit this deck",
                }
            )

    if average_mana_value is not None:
        if average_mana_value >= 4:
            findings.append(
                {
                    "severity": "warning",
                    "category": "mana curve",
                    "message": f"The average mana value is {average_mana_value}, which is somewhat high.",
                    "suggested_goal": "lower-mana cards that support this deck's strategy",
                }
            )
        else:
            findings.append(
                {
                    "severity": "ok",
                    "category": "mana curve",
                    "message": f"The average mana value is {average_mana_value}.",
                    "suggested_goal": None,
                }
            )

    meaningful_roles = {
        role: count
        for role, count in role_counts.items()
        if role not in {"land", "creature", "spell"}
    }

    themes = [
        role
        for role, _ in Counter(meaningful_roles).most_common(8)
    ]

    return {
        "deck": serialize_deck(deck),
        "summary": {
            "total_cards": total_cards,
            "land_cards": land_cards,
            "nonland_cards": nonland_cards,
            "average_mana_value": average_mana_value,
        },
        "themes": themes,
        "role_counts": dict(role_counts),
        "type_counts": dict(type_counts),
        "color_counts": dict(color_counts),
        "findings": findings,
    }