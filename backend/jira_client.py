import os
import httpx
from dotenv import load_dotenv

load_dotenv()

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "")
# Override via JIRA_ISSUE_TYPE env var if your project uses e.g. "Story" or "Bug"
JIRA_ISSUE_TYPE = os.getenv("JIRA_ISSUE_TYPE", "Task")

AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(auth=AUTH, headers=HEADERS, timeout=20)


def _raise_for_status(resp: httpx.Response) -> None:
    """Like raise_for_status() but includes Jira's error body in the message."""
    if resp.is_error:
        try:
            detail = resp.json()
            # Jira returns {"errorMessages": [...], "errors": {...}}
            msgs = detail.get("errorMessages", [])
            errs = detail.get("errors", {})
            combined = "; ".join(msgs + [f"{k}: {v}" for k, v in errs.items()])
            raise ValueError(f"Jira {resp.status_code}: {combined or resp.text}")
        except (ValueError, KeyError):
            raise
        except Exception:
            resp.raise_for_status()


async def get_issue_types() -> list[str]:
    """Return the issue type names available for JIRA_PROJECT_KEY."""
    async with _client() as client:
        resp = await client.get(
            f"{JIRA_BASE_URL}/rest/api/3/issue/createmeta",
            params={"projectKeys": JIRA_PROJECT_KEY, "expand": "projects.issuetypes"},
        )
        _raise_for_status(resp)
    projects = resp.json().get("projects", [])
    if not projects:
        return []
    return [it["name"] for it in projects[0].get("issuetypes", [])]


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
    _raise_for_status(resp)
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


async def _resolve_issue_type(client: httpx.AsyncClient) -> str:
    """
    Return the best available issue type for the project.
    Preference order: env JIRA_ISSUE_TYPE → "Task" → "Story" → first non-Epic type.
    """
    try:
        resp = await client.get(
            f"{JIRA_BASE_URL}/rest/api/3/issue/createmeta",
            params={"projectKeys": JIRA_PROJECT_KEY, "expand": "projects.issuetypes"},
        )
        if resp.is_error:
            return JIRA_ISSUE_TYPE  # fall back silently
        projects = resp.json().get("projects", [])
        if not projects:
            return JIRA_ISSUE_TYPE
        available = [it["name"] for it in projects[0].get("issuetypes", [])]
        if not available:
            return JIRA_ISSUE_TYPE
        # Return the configured type if it's available
        if JIRA_ISSUE_TYPE in available:
            return JIRA_ISSUE_TYPE
        # Prefer common subtask-free types
        for preferred in ("Task", "Story", "Bug"):
            if preferred in available:
                return preferred
        # Last resort: first non-Epic type
        return next((t for t in available if t != "Epic"), available[0])
    except Exception:
        return JIRA_ISSUE_TYPE


async def create_ticket(
    summary: str,
    description: str = "",
    priority: str = "Medium",
    story_points: int | None = None,
) -> dict:
    """Create a new Jira issue and return its key and URL.

    Story points (customfield_10016) are set via a follow-up edit call because
    Jira often excludes that field from the create-issue screen.
    """
    async with _client() as client:
        issue_type = await _resolve_issue_type(client)

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
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
            }
        }

        resp = await client.post(f"{JIRA_BASE_URL}/rest/api/3/issue", json=body)
        _raise_for_status(resp)
        data = resp.json()
        issue_key = data["key"]

        # Set story points via edit — uses the edit screen which is usually more permissive
        if story_points is not None:
            edit_body = {"fields": {"customfield_10016": story_points}}
            edit_resp = await client.put(
                f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}", json=edit_body
            )
            # Silently ignore if the field is still not editable on this project
            if edit_resp.status_code not in (200, 204):
                pass  # ticket was created; just skip points

    return {
        "key": issue_key,
        "id": data["id"],
        "url": f"{JIRA_BASE_URL}/browse/{issue_key}",
        "issue_type": issue_type,
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
        _raise_for_status(resp)

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
