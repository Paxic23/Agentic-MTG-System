from typing import Any

from sqlalchemy.orm import Session

from app.agents.graphs.general_chat_graph import general_chat_graph
from app.core.config import get_settings
from app.llm.factory import get_llm_client
from app.llm.prompts.general_chat import build_general_chat_prompts
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
        deck_context = state.get("deck_context")
        tool_context = state.get("tool_context")
        messages = state.get("messages", [])

        settings = get_settings()
        llm_client = get_llm_client(settings)

        if not llm_client.is_enabled:
            return {
                "reply": (
                    "General chat is currently disabled because no LLM provider is configured. "
                    "Set LLM_PROVIDER and LLM_MODEL in the API environment to enable it."
                ),
                "used_deck_context": deck_context is not None,
                "referenced_deck_count": len(deck_context or []),
                "used_agentic_tools": any(
                    item.get("tool") != "deck_context_lookup"
                    for item in tool_trace
                ),
                "tool_trace": tool_trace,
            }

        system_prompt, user_prompt = build_general_chat_prompts(
            messages=messages,
            deck_context=deck_context,
            tool_context=tool_context,
        )

        completion = llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
        )

        return {
            "reply": completion.text,
            "used_deck_context": deck_context is not None,
            "referenced_deck_count": len(deck_context or []),
            "used_agentic_tools": any(
                item.get("tool") != "deck_context_lookup"
                for item in tool_trace
            ),
            "tool_trace": tool_trace,
        }
