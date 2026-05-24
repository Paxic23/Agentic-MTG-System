from sqlalchemy import Integer, String, Text, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    mana_cost: Mapped[str | None] = mapped_column(String, nullable=True)
    mana_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    type_line: Mapped[str | None] = mapped_column(String, nullable=True)
    oracle_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    colors: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    color_identity: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)