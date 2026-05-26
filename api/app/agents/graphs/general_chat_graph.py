import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Card, Deck, DeckCard
from app.schemas import GeneralChatRequest
from app.services.deck_service import serialize_card, serialize_deck


class GeneralChatState(TypedDict, total=False):
    request: GeneralChatRequest
    db: Session
    messages: list[dict[str, str]]
    latest_user_message: str
    deck_context: list[dict[str, Any]] | None
    selected_tool: Literal["none", "list_decks", "deck_quick_scan"]
    tool_context: dict[str, Any] | None
    tool_trace: list[dict[str, Any]]


def initialize_chat_state_node(state: GeneralChatState) -> dict[str, Any]:
    request = state["request"]
    messages = [
        {"role": message.role, "content": message.content}
        for message in request.messages
    ]

    latest_user_message = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            latest_user_message = (message.get("content") or "").strip()
            break

    return {
        "messages": messages,
        "latest_user_message": latest_user_message,
        "tool_trace": [],
        "selected_tool": "none",
        "tool_context": None,
    }


def build_deck_context_node(state: GeneralChatState) -> dict[str, Any]:
    request = state["request"]
    db = state["db"]

    if not request.include_deck_context:
        return {"deck_context": None}

    if request.deck_ids:
        decks = db.scalars(
            select(Deck)
            .where(Deck.id.in_(request.deck_ids))
            .order_by(Deck.created_at.desc())
        ).all()
    else:
        decks = db.scalars(select(Deck).order_by(Deck.created_at.desc())).all()

    context: list[dict[str, Any]] = []

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

    trace = list(state.get("tool_trace", []))
    trace.append(
        {
            "tool": "deck_context_lookup",
            "args": {
                "include_deck_context": request.include_deck_context,
                "deck_ids": request.deck_ids,
            },
            "ok": True,
            "summary": f"Loaded {len(context)} deck context record(s).",
        }
    )

    return {
        "deck_context": context,
        "tool_trace": trace,
    }


def select_tool_node(state: GeneralChatState) -> dict[str, Any]:
    text = state.get("latest_user_message", "").lower()

    wants_deck_list = (
        "list my decks" in text
        or "show my decks" in text
        or "what decks" in text
    )
    wants_deck_scan = "analyze deck" in text or "deck " in text and "problem" in text

    if wants_deck_list:
        return {"selected_tool": "list_decks"}

    if wants_deck_scan:
        return {"selected_tool": "deck_quick_scan"}

    return {"selected_tool": "none"}


def route_after_tool_selection(
    state: GeneralChatState,
) -> Literal["run_selected_tool", "finish_no_tool"]:
    if state.get("selected_tool") == "none":
        return "finish_no_tool"
    return "run_selected_tool"


def _extract_deck_id_from_message(message: str) -> int | None:
    match = re.search(r"\bdeck\s+(\d+)\b", message.lower())
    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None


def run_selected_tool_node(state: GeneralChatState) -> dict[str, Any]:
    db = state["db"]
    selected_tool = state.get("selected_tool", "none")
    trace = list(state.get("tool_trace", []))

    if selected_tool == "list_decks":
        decks = db.scalars(select(Deck).order_by(Deck.created_at.desc())).all()
        tool_context = {
            "decks": [
                {
                    "id": deck.id,
                    "name": deck.name,
                    "format": deck.format,
                }
                for deck in decks
            ]
        }
        trace.append(
            {
                "tool": "list_decks",
                "args": {},
                "ok": True,
                "summary": f"Found {len(decks)} deck(s).",
            }
        )
        return {
            "tool_context": tool_context,
            "tool_trace": trace,
        }

    if selected_tool == "deck_quick_scan":
        message = state.get("latest_user_message", "")
        deck_id = _extract_deck_id_from_message(message)

        if deck_id is None:
            trace.append(
                {
                    "tool": "deck_quick_scan",
                    "args": {"deck_id": None},
                    "ok": False,
                    "summary": "No numeric deck id found in message.",
                }
            )
            return {"tool_trace": trace}

        deck = db.get(Deck, deck_id)
        if deck is None:
            trace.append(
                {
                    "tool": "deck_quick_scan",
                    "args": {"deck_id": deck_id},
                    "ok": False,
                    "summary": "Deck not found.",
                }
            )
            return {"tool_trace": trace}

        rows = (
            db.execute(
                select(DeckCard, Card)
                .join(Card, DeckCard.card_id == Card.id)
                .where(DeckCard.deck_id == deck.id)
            )
            .all()
        )

        card_count = sum(deck_card.quantity for deck_card, _ in rows)
        unique_cards = len(rows)
        commander_count = sum(
            1 for deck_card, _ in rows if deck_card.is_commander
        )

        tool_context = {
            "deck": serialize_deck(deck),
            "quick_scan": {
                "card_count": card_count,
                "unique_cards": unique_cards,
                "commander_count": commander_count,
            },
        }
        trace.append(
            {
                "tool": "deck_quick_scan",
                "args": {"deck_id": deck.id},
                "ok": True,
                "summary": (
                    f"Scanned deck {deck.id} with {card_count} cards "
                    f"({commander_count} commander tags)."
                ),
            }
        )
        return {
            "tool_context": tool_context,
            "tool_trace": trace,
        }

    return {}


def finish_no_tool_node(state: GeneralChatState) -> dict[str, Any]:
    return {
        "tool_context": None,
    }


def build_general_chat_graph():
    graph = StateGraph(GeneralChatState)

    graph.add_node("initialize_chat_state", initialize_chat_state_node)
    graph.add_node("build_deck_context", build_deck_context_node)
    graph.add_node("select_tool", select_tool_node)
    graph.add_node("run_selected_tool", run_selected_tool_node)
    graph.add_node("finish_no_tool", finish_no_tool_node)

    graph.add_edge(START, "initialize_chat_state")
    graph.add_edge("initialize_chat_state", "build_deck_context")
    graph.add_edge("build_deck_context", "select_tool")
    graph.add_conditional_edges(
        "select_tool",
        route_after_tool_selection,
        {
            "run_selected_tool": "run_selected_tool",
            "finish_no_tool": "finish_no_tool",
        },
    )
    graph.add_edge("run_selected_tool", END)
    graph.add_edge("finish_no_tool", END)

    return graph.compile()


general_chat_graph = build_general_chat_graph()