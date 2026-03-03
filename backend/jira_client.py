import os
import httpx
from dotenv import load_dotenv

load_dotenv()

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "")

AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(auth=AUTH, headers=HEADERS, timeout=20)


async def _search_jql(client: httpx.AsyncClient, jql: str) -> list[dict]:
    """POST to /rest/api/3/search/jql and return raw issue list.

    The new endpoint uses cursor pagination (nextPageToken / isLast)
    instead of the old offset-based total field.
    """
    body = {
        "jql": jql,
        "maxResults": 100,
        "fields": [
            "summary", "status", "priority", "assignee",
            "customfield_10016", "labels", "description",
        ],
    }
    resp = await client.post(f"{JIRA_BASE_URL}/rest/api/3/search/jql", json=body)
    resp.raise_for_status()
    return resp.json().get("issues", [])


async def get_sprint_tickets() -> list[dict]:
    """Fetch issues for the current board.

    Tries the active sprint first (Scrum boards). Falls back to all
    project tickets when no sprint exists (Kanban boards).
    """
    sprint_jql = (
        f"project = {JIRA_PROJECT_KEY} "
        "AND sprint in openSprints() "
        "ORDER BY status ASC, priority DESC"
    )
    kanban_jql = (
        f"project = {JIRA_PROJECT_KEY} "
        "ORDER BY status ASC, priority DESC"
    )

    async with _client() as client:
        raw = await _search_jql(client, sprint_jql)
        if not raw:
            # No active sprint — Kanban board or sprint not started yet
            raw = await _search_jql(client, kanban_jql)
        data = {"issues": raw}

    tickets = []
    for issue in data.get("issues", []):
        fields = issue["fields"]
        tickets.append(
            {
                "id": issue["id"],
                "key": issue["key"],
                "summary": fields.get("summary", ""),
                "status": fields.get("status", {}).get("name", ""),
                "priority": fields.get("priority", {}).get("name", ""),
                "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
                "story_points": fields.get("customfield_10016"),
                "labels": fields.get("labels", []),
            }
        )
    return tickets


async def create_ticket(
    summary: str,
    description: str = "",
    priority: str = "Medium",
    story_points: int | None = None,
) -> dict:
    """Create a new Jira Task and return the created issue key and URL."""
    body: dict = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description or summary}],
                    }
                ],
            },
            "issuetype": {"name": "Task"},
            "priority": {"name": priority},
        }
    }
    if story_points is not None:
        body["fields"]["customfield_10016"] = story_points

    async with _client() as client:
        resp = await client.post(f"{JIRA_BASE_URL}/rest/api/3/issue", json=body)
        resp.raise_for_status()
        data = resp.json()

    return {
        "key": data["key"],
        "id": data["id"],
        "url": f"{JIRA_BASE_URL}/browse/{data['key']}",
    }

async def _get_transition_id(client: httpx.AsyncClient, issue_key: str, target_status: str) -> str | None:
    """Resolve target status name to a Jira transition ID."""
    resp = await client.get(f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions")
    resp.raise_for_status()
    for t in resp.json().get("transitions", []):
        if t["to"]["name"].lower() == target_status.lower():
            return t["id"]
    return None


async def move_ticket(issue_key: str, target_status: str) -> dict:
    """Transition a Jira ticket to the given status name."""
    async with _client() as client:
        transition_id = await _get_transition_id(client, issue_key, target_status)
        if not transition_id:
            raise ValueError(
                f"No transition to '{target_status}' found for {issue_key}. "
                "Check the workflow or status name."
            )
        body = {"transition": {"id": transition_id}}
        resp = await client.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions", json=body
        )
        resp.raise_for_status()

    return {"key": issue_key, "new_status": target_status}


async def get_sprint_stats() -> dict:
    """Return high-level statistics for the active sprint."""
    tickets = await get_sprint_tickets()

    total_points = 0
    done_points = 0
    blockers = 0

    for t in tickets:
        points = t.get("story_points") or 0
        total_points += points
        if t["status"].lower() == "done":
            done_points += points
        if t["priority"].lower() in ("highest", "blocker"):
            blockers += 1

    completion_pct = round((done_points / total_points * 100) if total_points else 0, 1)

    return {
        "total_tickets": len(tickets),
        "total_points": total_points,
        "done_points": done_points,
        "completion_pct": completion_pct,
        "blockers_count": blockers,
        "tickets_by_status": _group_by_status(tickets),
    }


def _group_by_status(tickets: list[dict]) -> dict[str, int]:
    groups: dict[str, int] = {}
    for t in tickets:
        groups[t["status"]] = groups.get(t["status"], 0) + 1
    return groups
