from pydantic import BaseModel


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


class DeckCoachRequest(BaseModel):
    deck_id: int
    goal: str | None = None
    suggestion_limit: int = 5
    max_mana_value: float | None = None
    include_tool_payloads: bool = True
