from fastapi import APIRouter, HTTPException

from models import BlockerCreate
from jira_client import get_sprint_tickets
import database

router = APIRouter(prefix="/api/blockers", tags=["Blockers"])


@router.get("")
async def list_blockers():
    """Return Highest-priority Jira tickets (auto-detected) plus manually added blockers."""
    try:
        tickets = await get_sprint_tickets()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    auto = [
        t for t in tickets
        if t.get("priority", "").lower() in ("highest", "blocker")
    ]
    manual = await database.list_manual_blockers()
    return {"auto": auto, "manual": manual}


@router.post("", status_code=201)
async def add_blocker(req: BlockerCreate):
    return await database.add_manual_blocker(req.text)


@router.delete("/{blocker_id}", status_code=204)
async def remove_blocker(blocker_id: str):
    deleted = await database.delete_manual_blocker(blocker_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Blocker not found")
