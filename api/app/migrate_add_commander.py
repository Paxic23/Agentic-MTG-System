from sqlalchemy import text

from app.db import engine


def migrate():
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                ALTER TABLE deck_cards
                ADD COLUMN IF NOT EXISTS is_commander BOOLEAN NOT NULL DEFAULT FALSE;
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_deck_single_commander
                ON deck_cards(deck_id)
                WHERE is_commander = TRUE;
                """
            )
        )

    print("Migration complete: deck_cards.is_commander is ready.")


if __name__ == "__main__":
    migrate()