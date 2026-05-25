import re
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Card, Deck, DeckCard
from app.schemas import DeckSuggestionRequest
from app.vector import ensure_collection, semantic_search_cards


BASIC_LAND_NAMES = {
    "Plains",
    "Island",
    "Swamp",
    "Mountain",
    "Forest",
    "Wastes",
}


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

def number_or_zero(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def int_or_zero(value: Any) -> int:
    if value is None:
        return 0
    return int(value)

def serialize_deck(deck: Deck):
    return {
        "id": deck.id,
        "name": deck.name,
        "format": deck.format,
        "description": deck.description,
        "created_at": deck.created_at,
    }


def get_deck_or_404(db: Session, deck_id: int) -> Deck:
    deck = db.get(Deck, deck_id)

    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    return deck


def get_deck_card_rows(db: Session, deck_id: int):
    return db.execute(
        select(DeckCard, Card)
        .join(Card, DeckCard.card_id == Card.id)
        .where(DeckCard.deck_id == deck_id)
    ).all()


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

    clean_line = re.sub(r"^(sb|sideboard|mb|mainboard|commander|companion)\s*:\s*", "", clean_line, flags=re.IGNORECASE)

    clean_line = re.sub(
        r"\s+\([A-Z0-9]{2,8}\)\s+\d+.*$",
        "",
        clean_line,
    )

    clean_line = re.sub(
        r"\s+\[[A-Z0-9]{2,8}\].*$",
        "",
        clean_line,
    )

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


def is_probably_moxfield_decklist(decklist: str) -> bool:
    patterned_lines = 0
    checked_lines = 0

    for raw_line in decklist.splitlines():
        clean_line = raw_line.strip()

        if not clean_line:
            continue

        parsed = parse_decklist_line(clean_line)
        if parsed is None:
            continue

        checked_lines += 1

        if re.search(r"\([A-Z0-9]{2,8}\)\s+[A-Z0-9]{2,8}-\d+", clean_line):
            patterned_lines += 1
        elif re.search(r"\[[A-Z0-9]{2,8}\]", clean_line):
            patterned_lines += 1

        if checked_lines >= 12:
            break

    return patterned_lines >= 2


def _normalize_import_name(name: str) -> str:
    normalized = re.sub(r"\s+", " ", name).strip().strip('"\'')

    # Normalize split/transform separators from inconsistent clipboard formats.
    normalized = re.sub(r"\s*//\s*", " // ", normalized)
    normalized = re.sub(r"\s*/\s*", " / ", normalized)

    # Strip set tags like (PLST) or [PLST], even when followed by collector tokens.
    normalized = re.sub(r"\s*[\[(][A-Z0-9]{2,8}[\])]", "", normalized)

    # Strip common trailing collector tokens: AKH-158, THB-9, #158, 158a.
    normalized = re.sub(r"\s+[A-Z0-9]{2,8}-\d+[a-zA-Z]?$", "", normalized)
    normalized = re.sub(r"\s+#\d+[a-zA-Z]?$", "", normalized)
    normalized = re.sub(r"\s+\d+[a-zA-Z]?$", "", normalized)

    # Remove optional trailing annotations from export formats.
    normalized = re.sub(r"\s*\*[^*]+\*$", "", normalized)

    return re.sub(r"\s+", " ", normalized).strip()


def _build_import_name_candidates(name: str) -> list[str]:
    cleaned = _normalize_import_name(name)

    if not cleaned:
        return []

    candidates: list[str] = []

    def add(candidate: str) -> None:
        value = re.sub(r"\s+", " ", candidate).strip()
        if value and value not in candidates:
            candidates.append(value)

    add(cleaned)

    if " / " in cleaned and " // " not in cleaned:
        add(cleaned.replace(" / ", " // "))

    if " // " in cleaned and " / " not in cleaned:
        add(cleaned.replace(" // ", " / "))

    if cleaned.startswith("A-"):
        add(cleaned[2:].strip())
    else:
        add(f"A-{cleaned}")

    split_name = cleaned.replace(" / ", " // ")
    if " // " in split_name:
        parts = [part.strip() for part in split_name.split(" // ") if part.strip()]
        for part in parts:
            add(part)
            add(f"A-{part}")

        if len(parts) == 2:
            # Some data sources index the reverse face order as a full card name.
            add(f"{parts[1]} // {parts[0]}")
            add(f"A-{parts[1]} // {parts[0]}")

    return candidates


def find_card_for_import(db: Session, raw_name: str) -> Card | None:
    candidates = _build_import_name_candidates(raw_name)

    if not candidates:
        return None

    for candidate in candidates:
        card = db.scalar(select(Card).where(Card.name.ilike(candidate)))
        if card:
            return card

    split_name = _normalize_import_name(raw_name).replace(" / ", " // ")
    if " // " not in split_name:
        return None

    parts = [part.strip() for part in split_name.split(" // ") if part.strip()]
    for part in parts:
        card = db.scalar(
            select(Card)
            .where(
                or_(
                    Card.name.ilike(part),
                    Card.name.ilike(f"{part} //%"),
                    Card.name.ilike(f"%// {part}"),
                    Card.name.ilike(f"A-{part}"),
                    Card.name.ilike(f"A-{part} //%"),
                )
            )
        )

        if card:
            return card

    return None


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


def analyze_deck_data(deck: Deck, rows: list[tuple[DeckCard, Card]]):
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

            mana_value = int_or_zero(card.mana_value)
            bucket = "7+" if mana_value >= 7 else str(mana_value)
            mana_curve[bucket] += quantity

    average_mana_value = None

    if nonland_cards > 0:
        weighted_mana_total = 0.0
        for deck_card, card in rows:
            is_land = card.type_line and "Land" in card.type_line
            if is_land:
                continue

            quantity = int_or_zero(deck_card.quantity)
            weighted_mana_total += number_or_zero(card.mana_value) * quantity

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


def check_deck_rules_data(deck: Deck, rows: list[tuple[DeckCard, Card]]):
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


def diagnose_deck_data(deck: Deck, rows: list[tuple[DeckCard, Card]]):
    total_cards = 0
    land_cards = 0
    nonland_cards = 0
    weighted_mana_total = 0.0

    role_counts = Counter()
    type_counts = Counter()
    color_counts = Counter()

    for deck_card, card in rows:
        quantity = int_or_zero(deck_card.quantity)
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
            weighted_mana_total += number_or_zero(card.mana_value) * quantity

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
                    "message": f"This deck has {land_cards} lands. Many Commander decks want roughly 35-38 lands, depending on ramp and curve.",
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
                    "message": f"This deck appears to have {role_counts['ramp / fixing']} ramp/fixing cards. Many Commander decks want around 8-12.",
                    "suggested_goal": "mana ramp and color fixing that fits this deck",
                }
            )

        if role_counts["card draw"] < 8:
            findings.append(
                {
                    "severity": "warning",
                    "category": "card draw",
                    "message": f"This deck appears to have {role_counts['card draw']} card-draw cards. Many Commander decks want around 8-12.",
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
                    "message": f"This deck appears to have {role_counts['board wipe']} board wipes. Many Commander decks want around 2-4.",
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


def suggest_cards_for_deck(
    deck: Deck,
    rows: list[tuple[DeckCard, Card]],
    request: DeckSuggestionRequest,
    db: Session,
):
    if not rows:
        return {
            "query_used": request.goal or "cards that improve this deck",
            "deck_colors": [],
            "allowed_colors": request.color_identity,
            "suggestions": [],
        }

    ensure_collection(recreate=False)

    deck_colors = {
        color
        for _, card in rows
        for color in (card.color_identity or [])
    }

    if request.color_identity is None:
        allowed_colors: set[str] | None = set(deck_colors) if deck_colors else None
    else:
        allowed_colors = {color.upper() for color in request.color_identity}

    query = build_deck_recommendation_query(
        deck=deck,
        rows=rows,
        goal=request.goal,
    )

    candidate_limit = max(request.limit * 8, 80)
    points = semantic_search_cards(query=query, limit=candidate_limit)

    if not points:
        return {
            "query_used": query,
            "deck_colors": sorted(deck_colors),
            "allowed_colors": sorted(allowed_colors) if allowed_colors is not None else None,
            "suggestions": [],
        }

    card_ids = [int(point.id) for point in points]
    score_by_id = {int(point.id): point.score for point in points}

    existing_ids = {card.id for _, card in rows}

    cards = db.scalars(select(Card).where(Card.id.in_(card_ids))).all()
    card_by_id = {card.id: card for card in cards}

    ranked_cards = []

    for card_id in card_ids:
        card = card_by_id.get(card_id)

        if not card:
            continue

        if card.id in existing_ids:
            continue

        if request.max_mana_value is not None and card.mana_value is not None:
            if card.mana_value > request.max_mana_value:
                continue

        if not card_color_identity_is_allowed(card, allowed_colors):
            continue

        ranked_cards.append(card)

        if len(ranked_cards) >= request.limit:
            break

    return {
        "query_used": query,
        "deck_colors": sorted(deck_colors),
        "allowed_colors": sorted(allowed_colors) if allowed_colors is not None else None,
        "suggestions": [
            {
                "score": score_by_id.get(card.id),
                "reason": "Semantic match for current deck themes and goal.",
                "card": serialize_card(card),
            }
            for card in ranked_cards
        ],
    }


def severity_label(severity: str) -> str:
    labels = {
        "error": "[ERROR]",
        "warning": "[WARN]",
        "info": "[INFO]",
        "ok": "[OK]",
    }

    return labels.get(severity, "-")


def build_deck_coach_report(
    deck: Deck,
    analysis: dict,
    rules_check: dict,
    diagnosis: dict,
    suggestions_response: dict | None,
    user_goal: str | None,
    ignored_categories: list[str] | None = None,
) -> str:
    summary = diagnosis.get("summary", {})
    themes = diagnosis.get("themes", [])
    findings = diagnosis.get("findings", [])
    issues = rules_check.get("issues", [])
    suggestions = suggestions_response.get("suggestions", []) if suggestions_response else []
    ignored_set = {
        category.strip().lower()
        for category in (ignored_categories or [])
        if category and category.strip()
    }
    filtered_findings = [
        finding
        for finding in findings
        if str(finding.get("category", "")).strip().lower() not in ignored_set
    ]

    lines = []

    lines.append(f"# Deck Coach Report: {deck.name}")
    lines.append("")

    if user_goal:
        lines.append(f"**Goal:** {user_goal}")
        lines.append("")

    if ignored_set:
        lines.append("**Ignoring categories:** " + ", ".join(sorted(ignored_set)))
        lines.append("")

    lines.append("## Snapshot")
    lines.append(f"- Format: {deck.format or 'Unknown'}")
    lines.append(f"- Total cards: {summary.get('total_cards', 0)}")
    lines.append(f"- Lands: {summary.get('land_cards', 0)}")
    lines.append(f"- Nonlands: {summary.get('nonland_cards', 0)}")
    lines.append(f"- Average mana value: {summary.get('average_mana_value') or '-'}")
    lines.append("")

    if themes:
        lines.append("## Detected themes")
        for theme in themes[:8]:
            lines.append(f"- {theme}")
        lines.append("")

    lines.append("## Rules check")
    if rules_check.get("is_valid"):
        lines.append("No major rules issues detected by the current checker.")
    else:
        if not issues:
            lines.append("No specific rules issues were returned.")
        for issue in issues[:8]:
            icon = severity_label(issue.get("severity", "info"))
            lines.append(f"- {icon} {issue.get('message')}")
    lines.append("")

    lines.append("## Diagnosis")
    if not filtered_findings:
        lines.append("No diagnosis findings yet. Add more cards to make the analysis more useful.")
    else:
        for finding in filtered_findings[:8]:
            icon = severity_label(finding.get("severity", "info"))
            category = finding.get("category", "general")
            message = finding.get("message", "")
            lines.append(f"- {icon} **{category}:** {message}")
    lines.append("")

    if suggestions:
        lines.append("## Suggested additions")
        for index, suggestion in enumerate(suggestions, start=1):
            card = suggestion["card"]
            score = suggestion.get("score")
            score_text = f" - score {score:.3f}" if isinstance(score, float) else ""

            lines.append(f"{index}. **{card['name']}**{score_text}")

            if card.get("mana_cost"):
                lines.append(f"   - Mana cost: {card['mana_cost']}")

            if card.get("type_line"):
                lines.append(f"   - Type: {card['type_line']}")

            if card.get("oracle_text"):
                oracle = card["oracle_text"].replace("\n", " ")
                if len(oracle) > 220:
                    oracle = oracle[:217] + "..."
                lines.append(f"   - Text: {oracle}")

            lines.append(
                "   - Why: Semantically matched against the deck diagnosis, current themes, and stated goal."
            )
    else:
        lines.append("## Suggested additions")
        lines.append("No suggestions were generated. Add more cards to the deck or re-index Qdrant if the vector database is empty.")

    lines.append("")

    lines.append("## Next action")
    if suggestions:
        lines.append("Review the suggested additions, add the ones that fit your budget/power level, then re-run Deck Health.")
    elif filtered_findings:
        first_goal = next(
            (
                finding.get("suggested_goal")
                for finding in filtered_findings
                if finding.get("suggested_goal")
            ),
            None,
        )

        if first_goal:
            lines.append(f"Try searching suggestions with this goal: **{first_goal}**")
        else:
            lines.append("Add more cards or choose a clearer improvement goal.")
    else:
        lines.append("Add more cards to make the coach more useful.")

    return "\n".join(lines)
