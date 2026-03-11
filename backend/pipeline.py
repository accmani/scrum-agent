"""
Pipeline state machine + WebSocket broadcaster.

Tracks autonomous code-fix pipeline runs and streams step-by-step
progress to all connected /ws/pipeline clients.

Message protocol (server → client):
  {"type": "pipeline_history",  "runs": [...]}          # sent on connect
  {"type": "pipeline_start",    "run_id", "issue_key", "issue_title"}
  {"type": "pipeline_step",     "run_id", "step", "label", "agent", "status"}
  {"type": "pipeline_complete", "run_id", "result": {...}}
  {"type": "pipeline_error",    "run_id", "error": "..."}
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from fastapi import WebSocket

# ── Step definitions (ordered) ──────────────────────────────────────────────

PIPELINE_STEPS = [
    ("analyzing",          "Analyzing Issue",              "scrum_master"),
    ("discovering_files",  "Scanning Repository",          "code_fix"),
    ("reading_code",       "Reading Source Code",          "code_fix"),
    ("generating_fix",     "Generating Code Fix",          "code_fix"),
    ("reviewing",          "Peer Code Review",             "code_reviewer"),
    ("generating_tests",   "Writing Unit Tests",           "test"),
    ("creating_branch",    "Creating Feature Branch",      "code_fix"),
    ("committing",         "Committing Changes",           "code_fix"),
    ("creating_pr",        "Opening Pull Request",         "code_fix"),
    ("moving_ticket",      "Updating Jira Ticket",         "jira"),
    ("complete",           "Pipeline Complete",            "code_fix"),
]

# ── In-memory state ──────────────────────────────────────────────────────────

_runs: dict[str, dict] = {}   # run_id → run dict
_MAX_RUNS = 20
_clients: set[WebSocket] = set()


# ── Internal helpers ─────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _broadcast(msg: dict) -> None:
    dead: set[WebSocket] = set()
    payload = json.dumps(msg)
    for ws in _clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


# ── Public API ────────────────────────────────────────────────────────────────

def create_run(issue_key: str, issue_title: str) -> str:
    """Create a new pipeline run and return its run_id."""
    run_id = uuid.uuid4().hex[:8]
    _runs[run_id] = {
        "run_id":      run_id,
        "issue_key":   issue_key,
        "issue_title": issue_title,
        "status":      "running",
        "steps":       [],
        "result":      None,
        "error":       None,
        "started_at":  _now(),
        "completed_at": None,
    }
    # Keep only the most recent N runs
    if len(_runs) > _MAX_RUNS:
        oldest = next(iter(_runs))
        del _runs[oldest]
    return run_id


async def emit_step(
    run_id: str,
    step: str,
    label: str,
    agent: str,
    status: str = "in_progress",
) -> None:
    """Record a pipeline step update and broadcast it to all clients."""
    run = _runs.get(run_id)
    if not run:
        return

    existing = next((s for s in run["steps"] if s["step"] == step), None)
    if existing:
        existing["status"] = status
        existing["updated_at"] = _now()
    else:
        run["steps"].append({
            "step":       step,
            "label":      label,
            "agent":      agent,
            "status":     status,
            "started_at": _now(),
        })

    await _broadcast({
        "type":   "pipeline_step",
        "run_id": run_id,
        "step":   step,
        "label":  label,
        "agent":  agent,
        "status": status,
    })


async def complete_run(run_id: str, result: dict) -> None:
    run = _runs.get(run_id)
    if run:
        run["status"]       = "complete"
        run["result"]       = result
        run["completed_at"] = _now()
    await _broadcast({"type": "pipeline_complete", "run_id": run_id, "result": result})


async def fail_run(run_id: str, error: str) -> None:
    run = _runs.get(run_id)
    if run:
        run["status"]       = "error"
        run["error"]        = error
        run["completed_at"] = _now()
    await _broadcast({"type": "pipeline_error", "run_id": run_id, "error": error})


async def start_run_broadcast(run_id: str, issue_key: str, issue_title: str) -> None:
    await _broadcast({
        "type":        "pipeline_start",
        "run_id":      run_id,
        "issue_key":   issue_key,
        "issue_title": issue_title,
    })


def get_runs() -> list[dict]:
    """Return all runs, newest first."""
    return list(reversed(list(_runs.values())))


# ── WebSocket handler ─────────────────────────────────────────────────────────

async def handle_pipeline_ws(websocket: WebSocket) -> None:
    """
    Accept a WebSocket connection and stream pipeline events.
    Sends the full run history on connect, then streams live updates.
    """
    await websocket.accept()
    _clients.add(websocket)
    try:
        # Send history immediately so the UI can render existing runs
        await websocket.send_text(
            json.dumps({"type": "pipeline_history", "runs": get_runs()})
        )
        # Keep alive — listen for client messages (catches disconnects immediately)
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except Exception:
        pass
    finally:
        _clients.discard(websocket)
