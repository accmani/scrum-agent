"""
Orchestrator — routes a Team Chat message to all specialized agents in parallel,
streams each agent's response back via WebSocket as it arrives.

WebSocket message protocol (server → client):
  {"type": "thinking",  "agent": "<name>", "display_name": "<label>", "color": "<color>"}
  {"type": "message",   "agent": "<name>", "display_name": "<label>", "color": "<color>", "text": "..."}
  {"type": "error",     "agent": "<name>", "display_name": "<label>", "color": "<color>", "text": "..."}
  {"type": "done"}
"""

import asyncio
import json
from fastapi import WebSocket

from agents import (
    ScrumMasterAgent,
    JiraAgent,
    GithubAgent,
    StandupAgent,
    PlanningAgent,
)
from jira_client import get_sprint_tickets
from github_client import get_open_issues


# One instance per agent type — they are stateless (no per-session memory)
_AGENTS = [
    ScrumMasterAgent(),
    JiraAgent(),
    GithubAgent(),
    StandupAgent(),
    PlanningAgent(),
]


async def _fetch_context() -> dict:
    """Fetch live Jira + GitHub data; return empty lists on failure."""
    try:
        tickets = await get_sprint_tickets()
    except Exception:
        tickets = []
    try:
        issues = await get_open_issues()
    except Exception:
        issues = []
    return {"tickets": tickets, "issues": issues}


async def _run_agent_and_send(
    agent,
    message: str,
    context: dict,
    websocket: WebSocket,
    send_lock: asyncio.Lock,
) -> None:
    """Run one agent and send its response through the WebSocket."""

    async def _send(payload: dict) -> None:
        async with send_lock:
            await websocket.send_text(json.dumps(payload))

    meta = {"agent": agent.name, "display_name": agent.display_name, "color": agent.color}

    # Notify the client that this agent is thinking
    await _send({"type": "thinking", **meta})

    try:
        text = await agent.run(message, context)
        await _send({"type": "message", "text": text, **meta})
    except Exception as exc:
        await _send({"type": "error", "text": str(exc), **meta})


async def handle_team_chat(websocket: WebSocket) -> None:
    """
    Main WebSocket handler.  Accepts text messages from the client,
    fans them out to all agents in parallel, and streams results back.
    """
    await websocket.accept()
    send_lock = asyncio.Lock()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                message = data.get("message", "").strip()
            except (json.JSONDecodeError, AttributeError):
                message = raw.strip()

            if not message:
                continue

            # Fetch live context once per message (shared across all agents)
            context = await _fetch_context()

            # Fan out to all agents concurrently
            await asyncio.gather(
                *[
                    _run_agent_and_send(agent, message, context, websocket, send_lock)
                    for agent in _AGENTS
                ]
            )

            # Signal to the client that all agents have responded
            async with send_lock:
                await websocket.send_text(json.dumps({"type": "done"}))

    except Exception:
        # Client disconnected or other error — silently exit
        pass
