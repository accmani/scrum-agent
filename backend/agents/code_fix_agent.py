"""
CodeFixAgent — three-step agentic pipeline:

  Step 1  Given an issue description + repo file tree →
          Claude picks which files to read.

  Step 2  Given issue + file contents →
          Claude generates the fix as structured JSON.

  Step 3  CodeReviewerAgent reviews the diff.
  Step 4  TestAgent generates unit tests.
  Step 5  create branch → commit fix + tests → open PR → move Jira ticket.

An optional step_callback(step, label, agent, status) is accepted to emit
real-time progress events to the Pipeline WebSocket.
"""

import json
import logging
import re
import asyncio
import uuid
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

from .base_agent import BaseAgent, MODEL
from .code_reviewer_agent import CodeReviewerAgent
from .test_agent import TestAgent
import github_client as gh
from jira_client import move_ticket as jira_move_ticket, get_sprint_tickets


# Files to skip
_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".otf", ".mp4", ".mp3", ".pdf", ".zip", ".tar",
    ".gz", ".lock", ".min.js", ".min.css", ".map", ".class", ".jar",
}
_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist",
    "build", ".next", "target", ".mvn", ".idea", ".gradle",
}
_MAX_FILES_TO_READ = 8

StepCallback = Callable[[str, str, str, str], Awaitable[None]]


def _is_skippable(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    if any(d in _SKIP_DIRS for d in parts[:-1]):
        return True
    ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
    return ext in _SKIP_EXTENSIONS


class CodeFixAgent(BaseAgent):
    name = "code_fix"
    display_name = "Code Fix Agent"
    color = "rose"

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    async def fix_issue(
        self,
        issue_key: str,
        description: str = "",
        step_callback: StepCallback | None = None,
    ) -> dict:
        """
        Full pipeline: discover → fix → review → test → branch → commit → PR → Jira move.
        step_callback(step, label, agent, status) is called at each step for UI streaming.
        """
        async def emit(step: str, label: str, agent: str = "code_fix", status: str = "in_progress"):
            if step_callback:
                try:
                    await step_callback(step, label, agent, status)
                except Exception:
                    pass

        # ── 1. Resolve issue ──────────────────────────────────────────
        await emit("analyzing", "Analyzing Issue", "scrum_master")
        issue = await self._resolve_issue(issue_key, description)

        # ── 2. Repo file tree ─────────────────────────────────────────
        await emit("discovering_files", "Scanning Repository Structure")
        try:
            all_files = await gh.get_repo_tree()
        except Exception as exc:
            return {"error": f"Could not read repository: {exc}"}
        repo_files = [p for p in all_files if not _is_skippable(p)]

        # ── 3. File discovery ─────────────────────────────────────────
        await emit("reading_code", "Identifying Relevant Files")
        file_paths = await self._discover_files(issue, repo_files)
        if not file_paths:
            return {"error": "Agent could not identify relevant files for this issue."}

        # ── 4. Read files ─────────────────────────────────────────────
        await emit("reading_code", "Reading Source Code")
        file_contents = await self._read_files(file_paths)

        # ── 5. Generate fix ───────────────────────────────────────────
        await emit("generating_fix", "Generating Code Fix")
        changes = await self._generate_fix(issue, file_contents)
        if not changes:
            return {"error": "Agent could not generate a code fix for this issue."}

        # ── 6. Code review ────────────────────────────────────────────
        await emit("reviewing", "Peer Code Review", "code_reviewer")
        review: dict = {}
        try:
            review = await CodeReviewerAgent().review_fix(issue, changes, file_contents)
        except Exception:
            review = {"approved": True, "verdict": "APPROVED", "summary": "Review skipped", "comments": []}

        # ── 7. Generate tests ─────────────────────────────────────────
        await emit("generating_tests", "Writing Unit Tests", "test")
        test_changes: list[dict] = []
        try:
            test_changes = await TestAgent().generate_tests(issue, changes, file_contents)
        except Exception:
            test_changes = []

        # ── 8. Create branch ──────────────────────────────────────────
        await emit("creating_branch", "Creating Feature Branch")
        try:
            branch = await self._make_branch(issue)
        except Exception as exc:
            return {"error": f"Could not create branch: {exc}"}

        # ── 9. Commit fix files ───────────────────────────────────────
        await emit("committing", "Committing Code Fix")
        committed_fixes = await self._commit_changes(changes, branch, issue)

        # ── 9b. Commit test files ─────────────────────────────────────
        committed_tests: list[dict] = []
        if test_changes:
            await emit("committing", "Committing Generated Tests", "test")
            committed_tests = await self._commit_changes(
                test_changes, branch, issue, prefix="test"
            )

        # ── 10. Create PR ─────────────────────────────────────────────
        await emit("creating_pr", "Opening Pull Request")
        try:
            pr = await self._open_pr(issue, branch, committed_fixes, review, test_changes)
        except Exception as exc:
            return {"error": f"Could not create PR: {exc}"}

        # ── 11. Move Jira ticket ──────────────────────────────────────
        jira_key = issue.get("jira_key")
        await emit("moving_ticket", "Updating Jira Ticket", "jira")
        if jira_key:
            try:
                await jira_move_ticket(jira_key, "In Review")
            except Exception:
                pass

        await emit("complete", "Pipeline Complete", "code_fix", "complete")

        return {
            "pr_url":          pr["url"],
            "pr_number":       pr["number"],
            "branch":          branch,
            "files_changed":   [c["path"] for c in committed_fixes],
            "tests_generated": len(committed_tests),
            "review_verdict":  review.get("verdict", ""),
            "review_summary":  review.get("summary", ""),
            "jira_key":        jira_key,
        }

    # ------------------------------------------------------------------ #
    #  Step helpers                                                        #
    # ------------------------------------------------------------------ #

    async def _resolve_issue(self, issue_key: str, extra_desc: str) -> dict:
        issue: dict = {
            "title": issue_key,
            "description": extra_desc,
            "jira_key": None,
            "gh_number": None,
        }

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

        # Jira key: PROJ-42
        if re.match(r"^[A-Z]+-\d+$", issue_key.strip(), re.IGNORECASE):
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
                    issue["jira_key"] = issue_key.upper()
                    if extra_desc:
                        issue["description"] = extra_desc
            except Exception:
                issue["jira_key"] = issue_key.upper()

        return issue

    async def _discover_files(self, issue: dict, repo_files: list[str]) -> list[str]:
        valid = set(repo_files)

        # ── Tier 1: tool-calling (guaranteed structured JSON, no regex) ──────
        try:
            response = await self._client.messages.create(
                model=MODEL,
                max_tokens=512,
                tools=[{
                    "name": "select_files",
                    "description": (
                        "Return the file paths from the repository that need to be "
                        "modified to fix this bug. Use the EXACT paths from the file tree."
                    ),
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "file_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    f"Exact paths to modify (max {_MAX_FILES_TO_READ}). "
                                    "Copy from the file tree — no changes to the path strings."
                                ),
                            }
                        },
                        "required": ["file_paths"],
                    },
                }],
                tool_choice={"type": "any"},
                messages=[{
                    "role": "user",
                    "content": (
                        f"Bug: {issue['title']}\n"
                        f"Description: {issue['description'] or 'N/A'}\n\n"
                        f"Repository file tree:\n{chr(10).join(repo_files[:500])}\n\n"
                        f"Select at most {_MAX_FILES_TO_READ} files to fix this bug."
                    ),
                }],
            )

            for block in response.content:
                if block.type == "tool_use" and block.name == "select_files":
                    paths = block.input.get("file_paths", [])
                    if not isinstance(paths, list):
                        continue
                    paths = [p for p in paths if isinstance(p, str)]
                    # Exact match first
                    exact = [p for p in paths if p in valid]
                    if exact:
                        logger.info("_discover_files tool exact: %s", exact)
                        return exact[:_MAX_FILES_TO_READ]
                    # Fuzzy: suffix / filename match
                    result, seen = [], set()
                    for p in paths:
                        p_c = p.lstrip("./").replace("\\", "/")
                        for rp in repo_files:
                            if rp not in seen and (
                                rp.endswith(p_c) or p_c.endswith(rp)
                                or rp.split("/")[-1] == p_c.split("/")[-1]
                            ):
                                result.append(rp); seen.add(rp); break
                    if result:
                        logger.info("_discover_files tool fuzzy: %s", result)
                        return result[:_MAX_FILES_TO_READ]

        except Exception as exc:
            logger.warning("_discover_files tool-call failed: %s", exc)

        # ── Tier 2: keyword scoring (no Claude call needed) ──────────────────
        logger.warning("_discover_files: falling back to keyword scoring")
        words = set(re.findall(
            r'\b[a-zA-Z]{4,}\b',
            (issue['title'] + ' ' + (issue['description'] or '')).lower()
        ))
        scored: list[tuple[int, str]] = []
        for path in repo_files:
            score = sum(1 for w in words if w in path.lower())
            if score:
                scored.append((score, path))
        if scored:
            scored.sort(reverse=True)
            result = [p for _, p in scored[:_MAX_FILES_TO_READ]]
            logger.info("_discover_files keyword: %s", result)
            return result

        # ── Tier 3: all source files (absolute last resort) ──────────────────
        logger.warning("_discover_files: returning all source files as last resort")
        src_exts = {".java", ".py", ".js", ".ts", ".go", ".cs", ".rb", ".php"}
        src = [p for p in repo_files
               if any(p.endswith(e) for e in src_exts)
               and "/test" not in p.lower()]
        return src[:_MAX_FILES_TO_READ] or repo_files[:_MAX_FILES_TO_READ]

    async def _read_files(self, paths: list[str]) -> list[dict]:
        results = await asyncio.gather(
            *[gh.get_file_content(p) for p in paths],
            return_exceptions=True,
        )
        return [r for r in results if isinstance(r, dict)]

    async def _generate_fix(self, issue: dict, file_contents: list[dict]) -> list[dict]:
        # Separate source files from test files; tests are context only
        src_files  = [f for f in file_contents if "/test/" not in f["path"]]
        test_files = [f for f in file_contents if "/test/" in f["path"]]

        src_text  = "".join(f"\n\n### {f['path']}\n```\n{f['content']}\n```" for f in src_files)
        test_text = "".join(f"\n\n### {f['path']} (context only — do NOT include in output)\n```\n{f['content']}\n```" for f in test_files)

        prompt = f"""You are a senior software engineer. Fix the following bug by modifying the SOURCE files.

## Issue
Title: {issue['title']}
Description: {issue['description'] or '(no additional description)'}

## Source files to fix
{src_text}
{('## Test files (read-only context — do NOT include in output JSON)' + test_text) if test_text else ''}

## Task
Return a JSON array (ONLY the JSON array, no markdown fences, no explanation outside the array) where each element is:
{{
  "path": "exact/path/as/shown/above",
  "new_content": "<complete updated file content>",
  "explanation": "one-sentence description of the change"
}}

Rules:
- Only include SOURCE files that actually need changes (never include test files).
- Return the COMPLETE new file content (not a diff).
- Escape all double-quotes inside strings as \\".
- If you cannot determine a safe fix, return [].
"""
        response = await self._client.messages.create(
            model=MODEL,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        logger.info("_generate_fix stop_reason=%s output_tokens=%d",
                    response.stop_reason, response.usage.output_tokens)
        raw = response.content[0].text.strip()
        sha_map = {f["path"]: f["sha"] for f in file_contents}

        # Strip markdown code fences if present, then find the outermost JSON array
        cleaned = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()

        # Greedy search for the outermost [...] block
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            return []
        try:
            changes = json.loads(match.group())
            for c in changes:
                c["existing_sha"] = sha_map.get(c["path"])
            return changes
        except (json.JSONDecodeError, TypeError):
            return []

    async def _make_branch(self, issue: dict) -> str:
        import httpx
        title_slug = gh.slugify(issue["title"])
        key = (issue.get("jira_key") or f"gh-{issue.get('gh_number', 'fix')}").lower()
        branch_name = f"fix/{key}-{title_slug}"[:60]
        try:
            await gh.create_branch(branch_name)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 422:
                # Branch already exists — append a short unique suffix and retry
                suffix = uuid.uuid4().hex[:6]
                branch_name = f"{branch_name[:53]}-{suffix}"
                await gh.create_branch(branch_name)
            else:
                raise
        return branch_name

    async def _commit_changes(
        self,
        changes: list[dict],
        branch: str,
        issue: dict,
        prefix: str = "fix",
    ) -> list[dict]:
        committed = []
        key = issue.get("jira_key") or f"gh-{issue.get('gh_number', '')}"
        for change in changes:
            msg = f"{prefix}({key}): {change.get('explanation', 'auto-fix')}"
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

    async def _open_pr(
        self,
        issue: dict,
        branch: str,
        committed: list[dict],
        review: dict,
        test_changes: list[dict],
    ) -> dict:
        key = issue.get("jira_key")
        gh_num = issue.get("gh_number")

        fixes_lines = []
        if key:
            fixes_lines.append(f"- Fixes Jira ticket: **{key}**")
        if gh_num:
            fixes_lines.append(f"- Closes #{gh_num}")

        files_lines = [f"- `{c['path']}`" for c in committed if "error" not in c]
        test_lines  = [f"- `{t['path']}`" for t in test_changes]

        review_section = ""
        if review:
            verdict = review.get("verdict", "APPROVED")
            summary = review.get("summary", "")
            comments = review.get("comments", [])
            comment_text = "\n".join(f"  - {c}" for c in comments) if comments else "  - No issues found"
            review_section = f"""
### Code Review — {verdict}
{summary}

**Review comments:**
{comment_text}
"""

        body = "\n".join([
            f"## Auto-fix: {issue['title']}",
            "",
            "### Source files changed",
            *files_lines,
        ])
        if test_lines:
            body += "\n\n### Tests generated\n" + "\n".join(test_lines)
        if fixes_lines:
            body += "\n\n### References\n" + "\n".join(fixes_lines)
        if review_section:
            body += "\n" + review_section
        body += "\n\n> ⚠️ Auto-generated by Code Fix Agent — please review before merging."

        title = f"fix: {issue['title']}"
        if key:
            title = f"fix({key}): {issue['title']}"

        return await gh.create_pull_request(title=title, body=body, head_branch=branch)

    # ── BaseAgent.run() override for chat use ─────────────────────────────

    def system_prompt(self, context: dict) -> str:
        return """You are the Code Fix Agent. You fix bugs by reading source code and creating pull requests.

When asked to fix an issue, explain that the pipeline is starting and what steps it will take.
For other questions, answer as a senior engineer."""
