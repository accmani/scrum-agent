from fastapi import APIRouter, HTTPException

from jira_client import get_sprint_stats, get_sprint_tickets

router = APIRouter(prefix="/api/velocity", tags=["Velocity"])


@router.get("")
async def get_velocity():
    """
    Sprint velocity data: all stats from /api/jira/stats plus a per-assignee
    breakdown showing tickets assigned, completed, and story points.
    """
    try:
        stats = await get_sprint_stats()
        tickets = await get_sprint_tickets()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    assignee_breakdown: dict[str, dict] = {}
    for t in tickets:
        name = t.get("assignee") or "Unassigned"
        if name not in assignee_breakdown:
            assignee_breakdown[name] = {
                "assignee": name,
                "tickets":       0,
                "done":          0,
                "points":        0,
                "done_points":   0,
            }
        entry = assignee_breakdown[name]
        entry["tickets"] += 1
        pts = t.get("story_points") or 0
        entry["points"] += pts
        if t.get("status", "").lower() == "done":
            entry["done"] += 1
            entry["done_points"] += pts

    return {
        **stats,
        "assignee_breakdown": list(assignee_breakdown.values()),
    }
