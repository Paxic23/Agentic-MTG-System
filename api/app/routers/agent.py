from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.deck_coach import DeckCoachAgent
from app.agents.general_chat import GeneralChatAgent
from app.db import get_db
from app.schemas import DeckCoachRequest, GeneralChatRequest, GeneralChatResponse

router = APIRouter(tags=["agent"])


@router.post("/agent/deck-coach")
def deck_coach_agent(
    request: DeckCoachRequest,
    db: Session = Depends(get_db),
):
    agent = DeckCoachAgent()
    return agent.run(request=request, db=db)


@router.post("/agent/general-chat", response_model=GeneralChatResponse)
def general_chat_agent(
    request: GeneralChatRequest,
    db: Session = Depends(get_db),
):
    if not request.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    try:
        agent = GeneralChatAgent()
        return agent.run(request=request, db=db)
    except Exception as exc:
        # Keep this verbose during active development. Once stable, replace with
        # server-side logging and a generic 500 message.
        raise HTTPException(
            status_code=500,
            detail=f"{exc.__class__.__name__}: {exc}",
        ) from exc
