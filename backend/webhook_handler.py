"""
Jira Webhook receiver + background polling loop.

Two trigger modes:
  1. Webhook  — Jira calls POST /api/webhook/jira when an issue is created/updated.
                The pipeline fires if the issue has label "ai-fix".
  2. Polling  — A background asyncio task polls the Jira board every 30 seconds
                and fires the pipeline for any unprocessed "ai-fix" tickets.

Both modes call _run_pipeline() which runs CodeFixAgent → CodeReviewer → TestAgent
and streams progress via pipeline.py's WebSocket broadcaster.
"""

import asyncio
import logging

import pipeline as pl
from agents.code_fix_agent import CodeFixAgent
from jira_client import get_sprint_tickets

logger = logging.getLogger(__name__)

# Keys already processed in this session (avoids re-triggering on restart)
_processed_keys: set[str] = set()
_polling_task: asyncio.Task | None = None


# ── Public API ────────────────────────────────────────────────────────────────

async def handle_jira_webhook(payload: dict) -> dict:
    """
    Process a raw Jira webhook payload.
    Returns a status dict describing what action (if any) was taken.
    """
    event = payload.get("webhookEvent", "")
    if event not in ("jira:issue_created", "jira:issue_updated"):
        return {"status": "ignored", "reason": "not a create/update event"}

    issue = payload.get("issue") or {}
    fields = issue.get("fields") or {}
    labels = [lbl.get("name", "") for lbl in (fields.get("labels") or [])]

    if "ai-fix" not in labels and "auto-fix" not in labels:
        return {"status": "ignored", "reason": "no ai-fix or auto-fix label on issue"}

    issue_key = issue.get("key", "UNKNOWN")
    summary = fields.get("summary", issue_key)

    if issue_key in _processed_keys:
        return {"status": "ignored", "reason": f"{issue_key} already processed this session"}

    asyncio.create_task(_run_pipeline(issue_key, summary))
    return {"status": "triggered", "issue_key": issue_key, "issue_title": summary}


async def start_polling() -> None:
    """Start the background Jira polling loop (call once at startup)."""
    global _polling_task
    if _polling_task and not _polling_task.done():
        return
    _polling_task = asyncio.create_task(_poll_loop())
    logger.info("Jira polling started — checking every 30 s for 'ai-fix' tickets")


async def trigger_pipeline(issue_key: str, description: str = "") -> dict:
    """
    Manually trigger the pipeline for a given issue key.
    Used by the /api/trigger-pipeline endpoint for demo / chat-triggered runs.
    """
    if issue_key in _processed_keys:
        _processed_keys.discard(issue_key)  # allow re-trigger for demo purposes

    asyncio.create_task(_run_pipeline(issue_key, description or issue_key))
    return {"status": "triggered", "issue_key": issue_key}


def get_processed_keys() -> list[str]:
    return list(_processed_keys)


# ── Internal pipeline runner ──────────────────────────────────────────────────

async def _run_pipeline(issue_key: str, issue_title: str) -> None:
    """Full autonomous pipeline: analyze → fix → review → test → PR → move ticket."""
    _processed_keys.add(issue_key)
    run_id = pl.create_run(issue_key, issue_title)

    await pl.start_run_broadcast(run_id, issue_key, issue_title)
    logger.info(f"Pipeline started: run_id={run_id} issue={issue_key}")

    async def step(step_name: str, label: str, agent: str = "code_fix", status: str = "in_progress"):
        await pl.emit_step(run_id, step_name, label, agent, status)

    try:
        agent = CodeFixAgent()
        result = await agent.fix_issue(
            issue_key=issue_key,
            description=issue_title,
            step_callback=step,
        )

        if result.get("error"):
            await pl.fail_run(run_id, result["error"])
            logger.warning(f"Pipeline failed: run_id={run_id} error={result['error']}")
        else:
            await pl.complete_run(run_id, result)
            logger.info(f"Pipeline complete: run_id={run_id} pr={result.get('pr_url')}")

    except Exception as exc:
        await pl.fail_run(run_id, str(exc))
        logger.exception(f"Pipeline exception: run_id={run_id}")


# ── Polling loop ──────────────────────────────────────────────────────────────

async def _poll_loop() -> None:
    """Check Jira every 30 seconds for tickets labelled 'ai-fix'."""
    while True:
        try:
            await asyncio.sleep(30)
            tickets = await get_sprint_tickets()
            for ticket in tickets:
                if ticket["key"] in _processed_keys:
                    continue
                labels = ticket.get("labels", [])
                if "ai-fix" in labels or "auto-fix" in labels:
                    logger.info(f"Polling found ai-fix ticket: {ticket['key']}")
                    asyncio.create_task(_run_pipeline(ticket["key"], ticket["summary"]))
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error in Jira polling loop")
