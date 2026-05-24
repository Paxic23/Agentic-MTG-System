from sqlalchemy import select

from app.db import SessionLocal
from app.models import Card
from app.vector import ensure_collection, upsert_cards


def index_cards(limit: int = 1000, batch_size: int = 64, recreate: bool = True):
    ensure_collection(recreate=recreate)

    total_indexed = 0

    with SessionLocal() as db:
        cards = db.scalars(
            select(Card)
            .order_by(Card.id)
            .limit(limit)
        ).all()

        for start in range(0, len(cards), batch_size):
            batch = cards[start : start + batch_size]
            upsert_cards(batch)

            total_indexed += len(batch)
            print(f"Indexed {total_indexed}/{len(cards)} cards")

    print(f"Done. Indexed {total_indexed} cards into Qdrant.")


if __name__ == "__main__":
    index_cards(limit=1000, batch_size=64, recreate=True)