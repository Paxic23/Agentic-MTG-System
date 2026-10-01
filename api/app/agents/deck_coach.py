from typing import Any

from sqlalchemy.orm import Session

from app.agents.graphs.deck_coach_graph import deck_coach_graph
from app.agents.tool_log import log_agent_called
from app.schemas import DeckCoachRequest


class DeckCoachAgent:
    """
    Public agent wrapper used by the FastAPI router.

    The router should not care whether the workflow is implemented with
    plain Python, LangGraph, or a future graph with branching/checkpoints.
    """

    def run(
        self,
        *,
        request: DeckCoachRequest,
        db: Session,
    ) -> dict[str, Any]:
        log_agent_called("deck_coach")
        result = deck_coach_graph.invoke(
            {
                "request": request,
                "db": db,
            }
        )

        return result["final_response"]
