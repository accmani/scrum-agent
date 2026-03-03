import os
import httpx
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # "owner/repo"

BASE_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers=HEADERS, timeout=20)


async def get_open_issues() -> list[dict]:
    """Fetch open GitHub issues, excluding pull requests."""
    params = {"state": "open", "per_page": 100}
    async with _client() as client:
        resp = await client.get(
            f"{BASE_URL}/repos/{GITHUB_REPO}/issues", params=params
        )
        resp.raise_for_status()
        raw = resp.json()

    # GitHub returns PRs in the issues endpoint; filter them out
    issues = []
    for item in raw:
        if "pull_request" in item:
            continue
        issues.append(
            {
                "number": item["number"],
                "title": item["title"],
                "body": item.get("body", ""),
                "state": item["state"],
                "labels": [lbl["name"] for lbl in item.get("labels", [])],
                "assignee": (item.get("assignee") or {}).get("login", "Unassigned"),
                "created_at": item["created_at"],
                "url": item["html_url"],
            }
        )
    return issues


async def create_issue(title: str, body: str = "", labels: list[str] | None = None) -> dict:
    """Create a new GitHub issue and return its number and URL."""
    payload: dict = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    async with _client() as client:
        resp = await client.post(
            f"{BASE_URL}/repos/{GITHUB_REPO}/issues", json=payload
        )
        resp.raise_for_status()
        data = resp.json()

    return {
        "number": data["number"],
        "title": data["title"],
        "url": data["html_url"],
    }


async def close_issue(issue_number: int) -> dict:
    """Close a GitHub issue by its number."""
    payload = {"state": "closed"}
    async with _client() as client:
        resp = await client.patch(
            f"{BASE_URL}/repos/{GITHUB_REPO}/issues/{issue_number}", json=payload
        )
        resp.raise_for_status()
        data = resp.json()

    return {
        "number": data["number"],
        "state": data["state"],
        "url": data["html_url"],
    }
