import os
import base64
import re
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
    return httpx.AsyncClient(headers=HEADERS, timeout=30)


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------

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


async def get_issue(issue_number: int) -> dict:
    """Fetch a single GitHub issue by number."""
    async with _client() as client:
        resp = await client.get(f"{BASE_URL}/repos/{GITHUB_REPO}/issues/{issue_number}")
        resp.raise_for_status()
        item = resp.json()
    return {
        "number": item["number"],
        "title": item["title"],
        "body": item.get("body", ""),
        "state": item["state"],
        "labels": [lbl["name"] for lbl in item.get("labels", [])],
        "url": item["html_url"],
    }


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


# ---------------------------------------------------------------------------
# Git / repository operations (for code-fix pipeline)
# ---------------------------------------------------------------------------

async def get_default_branch() -> str:
    """Return the default branch name (e.g. 'main' or 'master')."""
    async with _client() as client:
        resp = await client.get(f"{BASE_URL}/repos/{GITHUB_REPO}")
        resp.raise_for_status()
    return resp.json().get("default_branch", "main")


async def get_branch_sha(branch: str) -> str:
    """Return the latest commit SHA on *branch*."""
    async with _client() as client:
        resp = await client.get(f"{BASE_URL}/repos/{GITHUB_REPO}/git/refs/heads/{branch}")
        resp.raise_for_status()
    return resp.json()["object"]["sha"]


async def get_repo_tree(branch: str | None = None) -> list[str]:
    """Return a flat list of all file paths in the repo (max ~10 k files)."""
    if branch is None:
        branch = await get_default_branch()
    sha = await get_branch_sha(branch)
    async with _client() as client:
        resp = await client.get(
            f"{BASE_URL}/repos/{GITHUB_REPO}/git/trees/{sha}",
            params={"recursive": "1"},
        )
        resp.raise_for_status()
    tree = resp.json().get("tree", [])
    return [item["path"] for item in tree if item["type"] == "blob"]


async def get_file_content(path: str, branch: str | None = None) -> dict:
    """
    Return {path, content (str), sha} for a single file.
    *sha* is needed when updating (committing) the file later.
    """
    if branch is None:
        branch = await get_default_branch()
    async with _client() as client:
        resp = await client.get(
            f"{BASE_URL}/repos/{GITHUB_REPO}/contents/{path}",
            params={"ref": branch},
        )
        resp.raise_for_status()
    data = resp.json()
    raw = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return {"path": path, "content": raw, "sha": data["sha"]}


async def create_branch(branch_name: str, from_branch: str | None = None) -> str:
    """Create a new branch and return its name."""
    if from_branch is None:
        from_branch = await get_default_branch()
    sha = await get_branch_sha(from_branch)
    payload = {"ref": f"refs/heads/{branch_name}", "sha": sha}
    async with _client() as client:
        resp = await client.post(
            f"{BASE_URL}/repos/{GITHUB_REPO}/git/refs", json=payload
        )
        resp.raise_for_status()
    return branch_name


async def commit_file(
    path: str,
    content: str,
    message: str,
    branch: str,
    existing_sha: str | None = None,
) -> dict:
    """
    Create or update *path* on *branch* with *content*.
    *existing_sha* is required when updating an existing file.
    Returns {path, sha, url}.
    """
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    payload: dict = {"message": message, "content": encoded, "branch": branch}
    if existing_sha:
        payload["sha"] = existing_sha

    async with _client() as client:
        resp = await client.put(
            f"{BASE_URL}/repos/{GITHUB_REPO}/contents/{path}", json=payload
        )
        resp.raise_for_status()
    data = resp.json()
    return {
        "path": path,
        "sha": data["content"]["sha"],
        "url": data["content"]["html_url"],
    }


async def create_pull_request(
    title: str,
    body: str,
    head_branch: str,
    base_branch: str | None = None,
) -> dict:
    """Open a pull request from *head_branch* → *base_branch*. Returns {number, url}."""
    if base_branch is None:
        base_branch = await get_default_branch()
    payload = {"title": title, "body": body, "head": head_branch, "base": base_branch}
    async with _client() as client:
        resp = await client.post(
            f"{BASE_URL}/repos/{GITHUB_REPO}/pulls", json=payload
        )
        resp.raise_for_status()
    data = resp.json()
    return {"number": data["number"], "url": data["html_url"]}


def slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a safe branch-name slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-")
