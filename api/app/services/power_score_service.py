from __future__ import annotations

from typing import Any

from app.models import Card, DeckCard
from app.services.edh_powerlevel_service import fetch_power_level_sync

DeckRows = list[tuple[DeckCard, Card]]


def build_moxfield_decklist(rows: DeckRows) -> str:
    """Render deck rows as a Moxfield-style list with a trailing COMMANDER section."""
    mainboard: list[str] = []
    commanders: list[str] = []

    for deck_card, card in sorted(rows, key=lambda row: row[1].name):
        line = f"{int(deck_card.quantity or 0)} {card.name}"
        if deck_card.is_commander:
            commanders.append(line)
        else:
            mainboard.append(line)

    lines = mainboard
    if commanders:
        lines = [*mainboard, "", "COMMANDER", *commanders]
    return "\n".join(lines)


def score_power_level(
    diagnosis: dict[str, Any],
    rows: DeckRows,
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    if not rows:
        return {"status": "skipped", "message": "Deck has no cards."}

    decklist = build_moxfield_decklist(rows)
    try:
        result = fetch_power_level_sync(decklist, use_cache=use_cache)
    # Scraping can fail for many reasons (site down, layout change, missing
    # Chromium); a failed power score must never break the coach flow.
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "message": f"Could not get a power level from edhpowerlevel.com: {exc}",
        }

    return {"status": "ok", **result}
