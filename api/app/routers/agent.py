from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.deck_coach import DeckCoachAgent
from app.db import get_db
from app.schemas import DeckCoachRequest

router = APIRouter(tags=["agent"])


@router.post("/agent/deck-coach")
def deck_coach_agent(
    request: DeckCoachRequest,
    db: Session = Depends(get_db),
):
    agent = DeckCoachAgent()
    return agent.run(request=request, db=db)
