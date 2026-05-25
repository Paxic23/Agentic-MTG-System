import json
from pathlib import Path

from sqlalchemy import select

from app.db import Base, engine, SessionLocal
from app.models import Card


DATA_PATH = Path("/data/AtomicCards.json")


def normalize_card(name: str, raw: dict) -> Card:
    return Card(
        name=name,
        mana_cost=raw.get("manaCost"),
        mana_value=raw.get("manaValue"),
        type_line=raw.get("type"),
        oracle_text=raw.get("text"),
        colors=raw.get("colors", []),
        color_identity=raw.get("colorIdentity", []),
        keywords=raw.get("keywords", []),
    )


def ingest(limit: int = 10000):
    Base.metadata.create_all(bind=engine)

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Could not find {DATA_PATH}")

    with DATA_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    cards_by_name = payload["data"]

    inserted = 0
    skipped = 0

    with SessionLocal() as db:
        for name, card_versions in cards_by_name.items():
            if inserted >= limit:
                break

            # AtomicCards usually stores a list under each card name.
            raw = card_versions[0] if isinstance(card_versions, list) else card_versions

            existing = db.scalar(select(Card).where(Card.name == name))
            if existing:
                skipped += 1
                continue

            card = normalize_card(name, raw)
            db.add(card)
            inserted += 1

        db.commit()

    print(f"Inserted {inserted} cards. Skipped {skipped} existing cards.")


if __name__ == "__main__":
    ingest(limit=80000)