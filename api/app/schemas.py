from typing import Any, Literal

from pydantic import BaseModel, Field


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
    ignore_categories: list[str] = Field(default_factory=list)


class CardPriceSearchRequest(BaseModel):
    names: list[str] = Field(default_factory=list)
    ids: list[int] = Field(default_factory=list)


class CardPriceRefreshRequest(BaseModel):
    force: bool = False


class GeneralChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class GeneralChatRequest(BaseModel):
    messages: list[GeneralChatMessage] = Field(default_factory=list)
    include_deck_context: bool = False
    deck_ids: list[int] = Field(default_factory=list)


class GeneralChatToolTrace(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    ok: bool = True
    summary: str | None = None


class GeneralChatResponse(BaseModel):
    reply: str
    used_deck_context: bool = False
    referenced_deck_count: int = 0
    used_agentic_tools: bool = False
    tool_trace: list[GeneralChatToolTrace] = Field(default_factory=list)
