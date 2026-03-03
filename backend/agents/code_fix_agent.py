"""
CodeFixAgent — two-step agentic pipeline:

  Step 1  Given an issue description + repo file tree →
          Claude picks which files to read.

  Step 2  Given issue + file contents →
          Claude generates the fix as structured JSON.

  Then:   create branch → commit each changed file → open PR → move Jira ticket.
"""

import json
import re
import asyncio

from .base_agent import BaseAgent, MODEL
import github_client as gh
from jira_client import move_ticket as jira_move_ticket, get_sprint_tickets


# Files to skip — typically too large or irrelevant for code fixes
_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".otf", ".mp4", ".mp3", ".pdf", ".zip", ".tar",
    ".gz", ".lock", ".min.js", ".min.css", ".map",
}
_SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next"}

# Max files Claude will read in one shot (guards against token overflow)
_MAX_FILES_TO_READ = 8


def _is_skippable(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    if any(d in _SKIP_DIRS for d in parts[:-1]):
        return True
    _, ext = path.rsplit(".", 1) if "." in path else (path, "")
    return f".{ext}" in _SKIP_EXTENSIONS


class CodeFixAgent(BaseAgent):
    name = "code_fix"
    display_name = "Code Fix Agent"
    color = "rose"

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    async def fix_issue(self, issue_key: str, description: str = "") -> dict:
        """
        Full pipeline: analyse → fix → branch → commit → PR → Jira move.

        Returns:
          {pr_url, pr_number, branch, files_changed, jira_key, error?}
        """
        # 1. Resolve issue details
        issue = await self._resolve_issue(issue_key, description)

        # 2. Get repo file tree (filtered)
        all_files = await gh.get_repo_tree()
        repo_files = [p for p in all_files if not _is_skippable(p)]

        # 3. Claude picks which files to read
        file_paths = await self._discover_files(issue, repo_files)
        if not file_paths:
            return {"error": "Agent could not identify relevant files for this issue."}

        # 4. Read selected files
        file_contents = await self._read_files(file_paths)

        # 5. Claude generates the fix
        changes = await self._generate_fix(issue, file_contents)
        if not changes:
            return {"error": "Agent could not generate a code fix for this issue."}

        # 6. Create branch
        branch = await self._make_branch(issue)

        # 7. Commit each changed file
        committed = await self._commit_changes(changes, branch, issue)

        # 8. Open Pull Request
        pr = await self._open_pr(issue, branch, committed)

        # 9. Move Jira ticket to "In Review" (best-effort)
        jira_key = issue.get("jira_key")
        if jira_key:
            try:
                await jira_move_ticket(jira_key, "In Review")
            except Exception:
                pass  # Don't fail the whole pipeline for Jira move errors

        return {
            "pr_url": pr["url"],
            "pr_number": pr["number"],
            "branch": branch,
            "files_changed": [c["path"] for c in committed],
            "jira_key": jira_key,
        }

    # ------------------------------------------------------------------ #
    #  Step helpers                                                        #
    # ------------------------------------------------------------------ #

    async def _resolve_issue(self, issue_key: str, extra_desc: str) -> dict:
        """
        Turn an issue key into {title, description, jira_key, gh_number}.
        Supports Jira keys (PROJ-42) and GitHub issue numbers (gh-15 or #15).
        """
        issue: dict = {"title": issue_key, "description": extra_desc, "jira_key": None, "gh_number": None}

        # GitHub issue: "gh-15" or "#15"
        gh_match = re.match(r"^(?:gh-|#)(\d+)$", issue_key.strip(), re.IGNORECASE)
        if gh_match:
            try:
                gh_issue = await gh.get_issue(int(gh_match.group(1)))
                issue.update({
                    "title": gh_issue["title"],
                    "description": gh_issue.get("body", "") or extra_desc,
                    "gh_number": gh_issue["number"],
                })
            except Exception:
                pass
            return issue

        # Jira issue: letters-digits (e.g. PROJ-42)
        jira_match = re.match(r"^[A-Z]+-\d+$", issue_key.strip(), re.IGNORECASE)
        if jira_match:
            try:
                tickets = await get_sprint_tickets()
                for t in tickets:
                    if t["key"].upper() == issue_key.upper():
                        issue.update({
                            "title": t["summary"],
                            "description": t.get("description", "") or extra_desc,
                            "jira_key": t["key"],
                        })
                        break
                else:
                    # Key not in current sprint — use whatever info we have
                    issue["jira_key"] = issue_key.upper()
                    if extra_desc:
                        issue["description"] = extra_desc
            except Exception:
                issue["jira_key"] = issue_key.upper()

        return issue

    async def _discover_files(self, issue: dict, repo_files: list[str]) -> list[str]:
        """Ask Claude which files are relevant for this issue."""
        file_list = "\n".join(repo_files[:500])  # send at most 500 paths to stay within token limit
        prompt = f"""You are a senior engineer helping to fix a bug.

## Issue
Title: {issue['title']}
Description: {issue['description'] or '(no additional description)'}

## Repository file tree
{file_list}

## Task
Return a JSON array (and ONLY the JSON array, no other text) of the file paths
most likely to need changes to fix this issue. Include at most {_MAX_FILES_TO_READ} paths.
Choose the most specific, relevant source files — avoid configs, lock files, or test snapshots
unless the bug is specifically about tests.

Example: ["src/auth/login.py", "src/utils/session.py"]
"""
        response = await self._client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Extract JSON array robustly
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            paths = json.loads(match.group())
            # Validate: only keep paths that actually exist in the repo
            valid = set(repo_files)
            return [p for p in paths if p in valid][:_MAX_FILES_TO_READ]
        except (json.JSONDecodeError, TypeError):
            return []

    async def _read_files(self, paths: list[str]) -> list[dict]:
        """Read file contents in parallel."""
        results = await asyncio.gather(
            *[gh.get_file_content(p) for p in paths],
            return_exceptions=True,
        )
        return [r for r in results if isinstance(r, dict)]

    async def _generate_fix(self, issue: dict, file_contents: list[dict]) -> list[dict]:
        """Ask Claude to generate code changes for the issue."""
        files_text = ""
        for f in file_contents:
            files_text += f"\n\n### {f['path']}\n```\n{f['content']}\n```"

        prompt = f"""You are a senior software engineer. Fix the following bug by modifying the source files provided.

## Issue
Title: {issue['title']}
Description: {issue['description'] or '(no additional description)'}

## Current file contents
{files_text}

## Task
Return a JSON array (and ONLY the JSON array, no other text) where each element describes one file change:
{{
  "path": "relative/path/to/file.py",
  "new_content": "<complete updated file content>",
  "explanation": "one-sentence explanation of the change"
}}

Rules:
- Only include files that actually need changes.
- Return the COMPLETE new file content for each changed file (not a diff).
- Do not add unnecessary imports, comments, or refactors beyond fixing the issue.
- If you cannot determine a safe fix, return an empty array [].
"""
        response = await self._client.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            changes = json.loads(match.group())
            # Attach the original file SHA for the commit API
            sha_map = {f["path"]: f["sha"] for f in file_contents}
            for c in changes:
                c["existing_sha"] = sha_map.get(c["path"])
            return changes
        except (json.JSONDecodeError, TypeError):
            return []

    async def _make_branch(self, issue: dict) -> str:
        """Create a fix branch with a deterministic name."""
        title_slug = gh.slugify(issue["title"])
        key = (issue.get("jira_key") or f"gh-{issue.get('gh_number', 'fix')}").lower()
        branch_name = f"fix/{key}-{title_slug}"[:60]
        await gh.create_branch(branch_name)
        return branch_name

    async def _commit_changes(self, changes: list[dict], branch: str, issue: dict) -> list[dict]:
        """Commit each file change to the branch."""
        committed = []
        key = issue.get("jira_key") or f"gh-{issue.get('gh_number', '')}"
        for change in changes:
            msg = f"fix({key}): {change.get('explanation', 'auto-fix')}"
            try:
                result = await gh.commit_file(
                    path=change["path"],
                    content=change["new_content"],
                    message=msg,
                    branch=branch,
                    existing_sha=change.get("existing_sha"),
                )
                committed.append({"path": change["path"], "url": result["url"]})
            except Exception as exc:
                committed.append({"path": change["path"], "error": str(exc)})
        return committed

    async def _open_pr(self, issue: dict, branch: str, committed: list[dict]) -> dict:
        """Create a Pull Request for the fix branch."""
        key = issue.get("jira_key")
        gh_num = issue.get("gh_number")

        # Build PR body
        fixes_lines = []
        if key:
            fixes_lines.append(f"- Fixes Jira ticket: **{key}**")
        if gh_num:
            fixes_lines.append(f"- Closes #{gh_num}")

        files_lines = [f"- `{c['path']}`" for c in committed if "error" not in c]
        body = "\n".join([
            f"## Auto-fix: {issue['title']}",
            "",
            "### What changed",
            *files_lines,
            "",
            "### References",
            *fixes_lines,
            "",
            "> ⚠️ Auto-generated by Code Fix Agent — please review before merging.",
        ])

        title = f"fix: {issue['title']}"
        if key:
            title = f"fix({key}): {issue['title']}"

        return await gh.create_pull_request(title=title, body=body, head_branch=branch)

    # ------------------------------------------------------------------ #
    #  BaseAgent.run() override — handles plain chat messages              #
    # ------------------------------------------------------------------ #

    def system_prompt(self, context: dict) -> str:
        return """You are the Code Fix Agent. You fix bugs by reading source code and creating pull requests.

When the user asks you to fix an issue:
- Tell them you are starting the pipeline and what you will do.
- The actual fix runs via the /api/fix-issue endpoint triggered by the UI.

When asked other questions, answer concisely as a senior engineer."""
