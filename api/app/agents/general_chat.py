from typing import Any

from sqlalchemy.orm import Session

from app.agents.graphs.general_chat_graph import general_chat_graph
from app.schemas import GeneralChatRequest


class GeneralChatAgent:
    def run(
        self,
        *,
        request: GeneralChatRequest,
        db: Session,
    ) -> dict[str, Any]:
        state = general_chat_graph.invoke(
            {
                "request": request,
                "db": db,
            }
        )

        tool_trace = state.get("tool_trace", [])

        return {
            "reply": state.get("final_reply", ""),
            "used_deck_context": request.include_deck_context,
            "referenced_deck_count": len(request.deck_ids) if request.include_deck_context else 0,
            "used_agentic_tools": bool(tool_trace),
            "tool_trace": tool_trace,
        }
