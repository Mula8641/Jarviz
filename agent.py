"""Agentic loop — LLM picks tools, executes them, iterates to a final answer."""
import json
import logging
from typing import Callable, Optional

from llm import chat_with_tools, chat
from tools import TOOL_DEFINITIONS, execute_tool

log = logging.getLogger("agent")

MAX_ITERATIONS = 6


def run(
    messages: list[dict],
    status_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Run the agentic loop.

    messages:         full conversation including system prompt + latest user turn
    status_callback:  optional fn(str) to push live status to the UI during tool use

    Returns the final text response to speak to the user.
    """
    working = list(messages)

    for iteration in range(MAX_ITERATIONS):
        log.info("Agent iteration %d/%d", iteration + 1, MAX_ITERATIONS)
        result = chat_with_tools(working, TOOL_DEFINITIONS)

        tool_calls = result.get("tool_calls")

        if not tool_calls:
            # LLM decided no more tools — return the final answer
            return result.get("content") or "I'm not sure how to help with that."

        # Append the assistant's tool-call turn to history
        working.append({
            "role": "assistant",
            "content": result.get("content") or "",
            "tool_calls": tool_calls,
        })

        # Execute every tool call and append results
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            raw_args = fn.get("arguments", "{}")

            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}

            if status_callback:
                label = name.replace("_", " ").title()
                status_callback(f"Using {label}...")

            tool_result = execute_tool(name, args)
            log.info("Tool %s → %s", name, tool_result[:120])

            working.append({
                "role": "tool",
                "tool_call_id": tc.get("id", f"call_{name}"),
                "name": name,
                "content": tool_result,
            })

    # Exceeded max iterations — ask the LLM to summarise what it found
    log.warning("Agent hit max iterations (%d) — forcing final answer", MAX_ITERATIONS)
    working.append({
        "role": "user",
        "content": "Based on everything above, give me a concise final answer.",
    })
    return chat(working)
