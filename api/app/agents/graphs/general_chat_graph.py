import json
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.client import ToolCall
from app.llm.factory import get_llm_client
from app.models import Card, Deck
from app.schemas import DeckSuggestionRequest, GeneralChatRequest
from app.services.deck_service import (
    get_deck_card_rows,
    serialize_card,
    serialize_deck,
    suggest_cards_for_deck,
)
from app.vector import ensure_collection, semantic_search_cards


MAX_ITERATIONS = 5

CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_decks",
            "description": (
                "List all of the user's decks with basic info (id, name, format). "
                "Use this first when the user asks about their collection or wants to "
                "know which decks they have before fetching details."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deck_details",
            "description": (
                "Get the full card list and stats for a specific deck. "
                "Use when the user asks about the contents of a named or numbered deck."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "deck_id": {
                        "type": "integer",
                        "description": "The numeric ID of the deck.",
                    }
                },
                "required": ["deck_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_cards",
            "description": (
                "Search the card database by name, oracle text, color identity, or mana value. "
                "Best for exact or partial name lookups and simple filter-based searches."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Partial card name to search for (case-insensitive).",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to match anywhere in the card's oracle text.",
                    },
                    "color": {
                        "type": "string",
                        "description": "Color identity filter — one of: W, U, B, R, G.",
                    },
                    "max_mana_value": {
                        "type": "number",
                        "description": "Only return cards with mana value at or below this number.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return. Defaults to 10.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_cards_semantic",
            "description": (
                "AI-powered semantic card search using natural language. "
                "Use for open-ended or thematic queries like 'cheap green ramp spells', "
                "'cards that punish opponents for drawing', or 'sacrifice outlets in black'. "
                "Prefer this over search_cards when the query is conceptual rather than name-based."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language description of the kinds of cards to find.",
                    },
                    "color": {
                        "type": "string",
                        "description": "Optional color identity filter (W, U, B, R, G).",
                    },
                    "max_mana_value": {
                        "type": "number",
                        "description": "Optional maximum mana value filter.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return. Defaults to 10.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_upgrades",
            "description": (
                "Find suggested card upgrades for a specific deck. "
                "Uses semantic search to match cards against the deck's themes, colors, and a stated goal. "
                "Use when the user asks what to add to a deck or how to improve it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "deck_id": {
                        "type": "integer",
                        "description": "ID of the deck to find upgrades for.",
                    },
                    "goal": {
                        "type": "string",
                        "description": (
                            "Optional improvement goal, e.g. 'more ramp', "
                            "'better removal', 'lower mana curve'."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of suggestions. Defaults to 10.",
                    },
                },
                "required": ["deck_id"],
            },
        },
    },
]


class GeneralChatState(TypedDict, total=False):
    request: GeneralChatRequest
    db: Session
    # Full OpenAI-format message history, including tool call/result turns
    messages: list[dict[str, Any]]
    pending_tool_calls: list[ToolCall]
    tool_trace: list[dict[str, Any]]
    iterations: int
    final_reply: str


def initialize_node(state: GeneralChatState) -> dict[str, Any]:
    request = state["request"]
    db = state["db"]

    deck_context_lines: list[str] = []

    if request.include_deck_context:
        if request.deck_ids:
            decks = db.scalars(
                select(Deck).where(Deck.id.in_(request.deck_ids))
            ).all()
        else:
            decks = db.scalars(select(Deck).order_by(Deck.created_at.desc())).all()

        if decks:
            deck_context_lines.append(
                "The user has pre-loaded the following decks (use get_deck_details for full card lists):"
            )
            for deck in decks:
                deck_context_lines.append(
                    f"  - Deck #{deck.id}: {deck.name} (format: {deck.format or 'unknown'})"
                )

    deck_context_section = (
        "\n\n" + "\n".join(deck_context_lines) if deck_context_lines else ""
    )

    system_prompt = (
        "You are a friendly, expert Magic: The Gathering assistant with access to the "
        "user's personal card collection and deck database. "
        "Use the provided tools to look up real data rather than guessing. "
        "When the user asks about their decks or cards, call the relevant tool first. "
        "You may call multiple tools across several turns before answering. "
        "Be conversational and direct. "
        "Never assume deck contents unless you have fetched them with a tool."
        + deck_context_section
    )

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for msg in request.messages:
        messages.append({"role": msg.role, "content": msg.content})

    return {
        "messages": messages,
        "tool_trace": [],
        "pending_tool_calls": [],
        "iterations": 0,
    }


def llm_decide_node(state: GeneralChatState) -> dict[str, Any]:
    settings = get_settings()
    llm_client = get_llm_client(settings)

    if not llm_client.is_enabled:
        return {
            "final_reply": (
                "General chat is currently disabled because no LLM provider is configured. "
                "Set LLM_PROVIDER and LLM_MODEL in the API environment to enable it."
            ),
            "pending_tool_calls": [],
        }

    iterations = state.get("iterations", 0)

    # At the iteration limit, force a text response instead of another tool call.
    force_text = iterations >= MAX_ITERATIONS

    decision = llm_client.decide_with_tools(
        messages=state.get("messages", []),
        tools=CHAT_TOOLS,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
        force_text=force_text,
    )

    if decision.tool_calls:
        messages = list(state.get("messages", []))
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in decision.tool_calls
                ],
            }
        )
        return {
            "messages": messages,
            "pending_tool_calls": decision.tool_calls,
            "iterations": iterations + 1,
        }

    return {
        "final_reply": decision.text or "",
        "pending_tool_calls": [],
        "iterations": iterations + 1,
    }


def route_after_llm(
    state: GeneralChatState,
) -> Literal["run_tools", "build_response"]:
    if state.get("pending_tool_calls"):
        return "run_tools"
    return "build_response"


def _execute_tool(tool_call: ToolCall, db: Session) -> Any:
    name = tool_call.name
    args = tool_call.arguments

    if name == "list_decks":
        decks = db.scalars(select(Deck).order_by(Deck.created_at.desc())).all()
        return {
            "decks": [
                {"id": deck.id, "name": deck.name, "format": deck.format}
                for deck in decks
            ]
        }

    if name == "get_deck_details":
        deck_id = args.get("deck_id")
        deck = db.get(Deck, deck_id)
        if deck is None:
            return {"error": f"Deck {deck_id} not found."}
        rows = get_deck_card_rows(db, deck_id)
        return {
            "deck": serialize_deck(deck),
            "cards": [
                {
                    "quantity": dc.quantity,
                    "is_commander": dc.is_commander,
                    "card": serialize_card(card),
                }
                for dc, card in rows
            ],
        }

    if name == "search_cards":
        stmt = select(Card)
        if args.get("name"):
            stmt = stmt.where(Card.name.ilike(f"%{args['name']}%"))
        if args.get("text"):
            stmt = stmt.where(Card.oracle_text.ilike(f"%{args['text']}%"))
        if args.get("color"):
            stmt = stmt.where(Card.color_identity.contains([args["color"].upper()]))
        if args.get("max_mana_value") is not None:
            stmt = stmt.where(Card.mana_value <= args["max_mana_value"])
        limit = int(args.get("limit", 10))
        stmt = stmt.order_by(Card.name).limit(limit)
        cards = db.scalars(stmt).all()
        return {"cards": [serialize_card(c) for c in cards]}

    if name == "search_cards_semantic":
        query = args.get("query", "")
        limit = int(args.get("limit", 10))
        ensure_collection(recreate=False)
        candidate_limit = max(limit * 5, 50)
        points = semantic_search_cards(query=query, limit=candidate_limit)

        if not points:
            return {"cards": []}

        card_ids = [int(p.id) for p in points]
        score_by_id = {int(p.id): p.score for p in points}

        stmt = select(Card).where(Card.id.in_(card_ids))
        if args.get("color"):
            stmt = stmt.where(Card.color_identity.contains([args["color"].upper()]))
        if args.get("max_mana_value") is not None:
            stmt = stmt.where(Card.mana_value <= args["max_mana_value"])

        db_cards = db.scalars(stmt).all()
        card_by_id = {c.id: c for c in db_cards}
        ranked = [card_by_id[cid] for cid in card_ids if cid in card_by_id][:limit]

        return {
            "cards": [
                {**serialize_card(c), "score": score_by_id.get(c.id)}
                for c in ranked
            ]
        }

    if name == "find_upgrades":
        deck_id = args.get("deck_id")
        deck = db.get(Deck, deck_id)
        if deck is None:
            return {"error": f"Deck {deck_id} not found."}
        rows = get_deck_card_rows(db, deck_id)
        return suggest_cards_for_deck(
            deck=deck,
            rows=rows,
            request=DeckSuggestionRequest(
                goal=args.get("goal"),
                limit=int(args.get("limit", 10)),
            ),
            db=db,
        )

    return {"error": f"Unknown tool: {name}"}


def run_tools_node(state: GeneralChatState) -> dict[str, Any]:
    db = state["db"]
    pending = state.get("pending_tool_calls", [])
    trace = list(state.get("tool_trace", []))
    messages = list(state.get("messages", []))

    for tool_call in pending:
        try:
            result = _execute_tool(tool_call, db)
            ok = True
            summary = f"Tool '{tool_call.name}' completed successfully."
        except Exception as exc:
            result = {"error": str(exc)}
            ok = False
            summary = f"Tool '{tool_call.name}' failed: {exc}"

        trace.append(
            {
                "tool": tool_call.name,
                "args": tool_call.arguments,
                "ok": ok,
                "summary": summary,
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            }
        )

    return {
        "messages": messages,
        "tool_trace": trace,
        "pending_tool_calls": [],
    }


def build_response_node(state: GeneralChatState) -> dict[str, Any]:
    # final_reply is already set by llm_decide_node; this node is a structural endpoint.
    return {}


def build_general_chat_graph():
    graph = StateGraph(GeneralChatState)

    graph.add_node("initialize", initialize_node)
    graph.add_node("llm_decide", llm_decide_node)
    graph.add_node("run_tools", run_tools_node)
    graph.add_node("build_response", build_response_node)

    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "llm_decide")
    graph.add_conditional_edges(
        "llm_decide",
        route_after_llm,
        {
            "run_tools": "run_tools",
            "build_response": "build_response",
        },
    )
    graph.add_edge("run_tools", "llm_decide")  # agentic loop
    graph.add_edge("build_response", END)

    return graph.compile()


general_chat_graph = build_general_chat_graph()
