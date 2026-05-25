from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.deck_coach import DeckCoachAgent
from app.core.config import get_settings
from app.db import get_db
from app.llm.factory import get_llm_client
from app.llm.prompts.general_chat import build_general_chat_prompts
from app.models import Card, Deck, DeckCard
from app.schemas import DeckCoachRequest, GeneralChatRequest, GeneralChatResponse
from app.services.deck_service import serialize_card, serialize_deck

router = APIRouter(tags=["agent"])


@router.post("/agent/deck-coach")
def deck_coach_agent(
    request: DeckCoachRequest,
    db: Session = Depends(get_db),
):
    agent = DeckCoachAgent()
    return agent.run(request=request, db=db)


def _build_deck_context(
    *,
    db: Session,
    include_deck_context: bool,
    deck_ids: list[int],
) -> list[dict] | None:
    if not include_deck_context:
        return None

    if deck_ids:
        decks = db.scalars(
            select(Deck)
            .where(Deck.id.in_(deck_ids))
            .order_by(Deck.created_at.desc())
        ).all()
    else:
        decks = db.scalars(select(Deck).order_by(Deck.created_at.desc())).all()

    if not decks:
        return []

    context: list[dict] = []

    for deck in decks:
        rows = (
            db.execute(
                select(DeckCard, Card)
                .join(Card, DeckCard.card_id == Card.id)
                .where(DeckCard.deck_id == deck.id)
                .order_by(Card.name)
            )
            .all()
        )

        cards = [
            {
                "quantity": deck_card.quantity,
                "is_commander": deck_card.is_commander,
                "card": serialize_card(card),
            }
            for deck_card, card in rows
        ]

        context.append(
            {
                "deck": serialize_deck(deck),
                "cards": cards,
            }
        )

    return context


@router.post("/agent/general-chat", response_model=GeneralChatResponse)
def general_chat_agent(
    request: GeneralChatRequest,
    db: Session = Depends(get_db),
):
    if not request.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    settings = get_settings()
    llm_client = get_llm_client(settings)

    if not llm_client.is_enabled:
        return GeneralChatResponse(
            reply=(
                "General chat is currently disabled because no LLM provider is configured. "
                "Set LLM_PROVIDER and LLM_MODEL in the API environment to enable it."
            ),
            used_deck_context=False,
            referenced_deck_count=0,
        )

    deck_context = _build_deck_context(
        db=db,
        include_deck_context=request.include_deck_context,
        deck_ids=request.deck_ids,
    )

    messages = [
        {"role": message.role, "content": message.content}
        for message in request.messages
    ]

    system_prompt, user_prompt = build_general_chat_prompts(
        messages=messages,
        deck_context=deck_context,
    )

    completion = llm_client.complete(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
    )

    return GeneralChatResponse(
        reply=completion.text,
        used_deck_context=deck_context is not None,
        referenced_deck_count=len(deck_context or []),
    )
