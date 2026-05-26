# In api/app/schemas.py:
# 1) change `from typing import Literal` to:
# from typing import Any, Literal
#
# 2) Replace GeneralChatResponse with these two classes.

class GeneralChatToolTrace(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    ok: bool = True
    summary: str | None = None
    error: str | None = None


class GeneralChatResponse(BaseModel):
    reply: str
    used_deck_context: bool = False
    referenced_deck_count: int = 0
    tool_trace: list[GeneralChatToolTrace] = Field(default_factory=list)
