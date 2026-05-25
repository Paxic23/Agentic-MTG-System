from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.tools import (
    resolve_coach_goal,
    run_analysis_tool,
    run_diagnosis_tool,
    run_llm_report_enhancement_tool,
    run_report_tool,
    run_rules_check_tool,
    run_suggestion_tool,
)
from app.models import Card, Deck, DeckCard
from app.schemas import DeckCoachRequest
from app.services.deck_service import (
    get_deck_card_rows,
    get_deck_or_404,
    serialize_deck,
)

DeckRows = list[tuple[DeckCard, Card]]


class DeckCoachState(TypedDict, total=False):
    request: DeckCoachRequest
    db: Session
    deck: Deck
    rows: DeckRows
    analysis: dict[str, Any]
    rules_check: dict[str, Any]
    diagnosis: dict[str, Any]
    goal_used: str | None
    suggestions_response: dict[str, Any]
    coach_report: str
    llm: dict[str, Any]
    final_response: dict[str, Any]


def load_deck_node(state: DeckCoachState) -> dict[str, Any]:
    request = state["request"]
    db = state["db"]

    deck = get_deck_or_404(db, request.deck_id)
    rows = get_deck_card_rows(db, request.deck_id)

    return {
        "deck": deck,
        "rows": rows,
    }


def route_after_load(
    state: DeckCoachState,
) -> Literal["empty_deck_response", "analyze_deck"]:
    if not state.get("rows"):
        return "empty_deck_response"
    return "analyze_deck"


def empty_deck_response_node(state: DeckCoachState) -> dict[str, Any]:
    request = state["request"]
    deck = state["deck"]
    goal_used = resolve_coach_goal(request.goal)

    response: dict[str, Any] = {
        "deck": serialize_deck(deck),
        "goal_used": goal_used,
        "coach_report": (
            f"# Deck Coach Report: {deck.name}\n\n"
            "This deck has no cards yet. Add or import a decklist first, "
            "then run the coach again."
        ),
    }

    if request.include_tool_payloads:
        response["tool_payloads"] = {}

    return {"final_response": response}


def analyze_deck_node(state: DeckCoachState) -> dict[str, Any]:
    return {
        "analysis": run_analysis_tool(
            deck=state["deck"],
            rows=state["rows"],
        )
    }


def check_rules_node(state: DeckCoachState) -> dict[str, Any]:
    return {
        "rules_check": run_rules_check_tool(
            deck=state["deck"],
            rows=state["rows"],
        )
    }


def diagnose_deck_node(state: DeckCoachState) -> dict[str, Any]:
    return {
        "diagnosis": run_diagnosis_tool(
            deck=state["deck"],
            rows=state["rows"],
        )
    }


def choose_goal_node(state: DeckCoachState) -> dict[str, Any]:
    request = state["request"]

    return {
        "goal_used": resolve_coach_goal(request.goal)
    }


def suggest_cards_node(state: DeckCoachState) -> dict[str, Any]:
    request = state["request"]

    return {
        "suggestions_response": run_suggestion_tool(
            deck=state["deck"],
            rows=state["rows"],
            db=state["db"],
            goal=state["goal_used"],
            limit=request.suggestion_limit,
            max_mana_value=request.max_mana_value,
        )
    }


def build_report_node(state: DeckCoachState) -> dict[str, Any]:
    request = state["request"]

    return {
        "coach_report": run_report_tool(
            deck=state["deck"],
            analysis=state["analysis"],
            rules_check=state["rules_check"],
            diagnosis=state["diagnosis"],
            suggestions_response=state["suggestions_response"],
            user_goal=request.goal,
        )
    }


def enhance_report_with_llm_node(state: DeckCoachState) -> dict[str, Any]:
    result = run_llm_report_enhancement_tool(
        deck=state["deck"],
        analysis=state["analysis"],
        rules_check=state["rules_check"],
        diagnosis=state["diagnosis"],
        suggestions_response=state["suggestions_response"],
        goal_used=state.get("goal_used"),
        deterministic_report=state["coach_report"],
    )

    return {
        "coach_report": result["coach_report"],
        "llm": result["llm"],
    }


def build_response_node(state: DeckCoachState) -> dict[str, Any]:
    request = state["request"]

    response: dict[str, Any] = {
        "deck": serialize_deck(state["deck"]),
        "goal_used": state["goal_used"],
        "coach_report": state["coach_report"],
    }

    if request.include_tool_payloads:
        response["tool_payloads"] = {
            "analysis": state["analysis"],
            "rules_check": state["rules_check"],
            "diagnosis": state["diagnosis"],
            "suggestions": state["suggestions_response"],
            "llm": state.get("llm", {}),
        }

    return {"final_response": response}


def build_deck_coach_graph():
    graph = StateGraph(DeckCoachState)

    graph.add_node("load_deck", load_deck_node)
    graph.add_node("empty_deck_response", empty_deck_response_node)
    graph.add_node("analyze_deck", analyze_deck_node)
    graph.add_node("check_rules", check_rules_node)
    graph.add_node("diagnose_deck", diagnose_deck_node)
    graph.add_node("choose_goal", choose_goal_node)
    graph.add_node("suggest_cards", suggest_cards_node)
    graph.add_node("build_report", build_report_node)
    graph.add_node("enhance_report_with_llm", enhance_report_with_llm_node)
    graph.add_node("build_response", build_response_node)

    graph.add_edge(START, "load_deck")
    graph.add_conditional_edges(
        "load_deck",
        route_after_load,
        {
            "empty_deck_response": "empty_deck_response",
            "analyze_deck": "analyze_deck",
        },
    )
    graph.add_edge("empty_deck_response", END)
    graph.add_edge("analyze_deck", "check_rules")
    graph.add_edge("check_rules", "diagnose_deck")
    graph.add_edge("diagnose_deck", "choose_goal")
    graph.add_edge("choose_goal", "suggest_cards")
    graph.add_edge("suggest_cards", "build_report")
    graph.add_edge("build_report", "enhance_report_with_llm")
    graph.add_edge("enhance_report_with_llm", "build_response")
    graph.add_edge("build_response", END)

    return graph.compile()


deck_coach_graph = build_deck_coach_graph()
