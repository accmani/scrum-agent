import json
import re
import os
from dotenv import load_dotenv

# override=True forces .env values even if the key exists in the OS environment
load_dotenv(override=True)

import anthropic
from jira_client import get_sprint_tickets, create_ticket, move_ticket
from github_client import get_open_issues
from models import ChatMessage
from agents import ScrumMasterAgent, JiraAgent, GithubAgent, StandupAgent, PlanningAgent, CodeFixAgent

_NAMED_AGENTS = {
    "scrum_master": ScrumMasterAgent(),
    "jira":         JiraAgent(),
    "github":       GithubAgent(),
    "standup":      StandupAgent(),
    "planning":     PlanningAgent(),
    "code_fix":     CodeFixAgent(),
}

MODEL = "claude-sonnet-4-20250514"

# Pass api_key explicitly so it always comes from the freshly loaded .env
client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _build_system_prompt(tickets: list[dict], issues: list[dict]) -> str:
    tickets_text = json.dumps(tickets, indent=2) if tickets else "No active sprint tickets."
    issues_text = json.dumps(issues, indent=2) if issues else "No open GitHub issues."

    return f"""You are an expert Scrum Master AI assistant. You have real-time access to the team's Jira sprint board and GitHub issues.

## Live Jira Sprint Board
{tickets_text}

## Live GitHub Issues
{issues_text}

## Your Capabilities
You can autonomously take the following actions by including a JSON code block in your response:

1. **Move a Jira ticket** to a new status:
```action
{{"action": "move_ticket", "issue_key": "PROJ-123", "target_status": "In Progress"}}
```

2. **Create a new Jira ticket**:
```action
{{"action": "create_ticket", "summary": "Ticket title", "description": "Details", "priority": "Medium", "story_points": 3}}
```

3. **Fix a bug and open a Pull Request** (reads code, generates fix, creates branch + PR):
```action
{{"action": "fix_issue", "issue_key": "PROJ-42", "description": "brief context about the bug"}}
```

## Guidelines
- Always reference specific ticket keys (e.g. PROJ-42) when discussing issues.
- Be concise, direct, and actionable — like a great Scrum Master.
- When you take an action, briefly explain what you did and why.
- Only take actions that the user explicitly requests or that are clearly implied.
- If you are unsure about a destructive action, ask for confirmation first.
"""


def _extract_action(text: str) -> dict | None:
    """Extract the first ```action ... ``` block from Claude's response."""
    match = re.search(r"```action\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _strip_action_block(text: str) -> str:
    """Remove action code blocks from the reply shown to the user."""
    return re.sub(r"```action\s*\{.*?\}\s*```", "", text, flags=re.DOTALL).strip()


async def run_agent(message: str, history: list[ChatMessage], agent: str | None = None) -> dict:
    """
    Run one turn of the Scrum Master agent.

    Returns:
        {
            "reply": str,          # Clean assistant message for the UI
            "action_result": dict | None  # Result of any executed action
        }
    """
    # Fetch live board context
    try:
        tickets = await get_sprint_tickets()
    except Exception:
        tickets = []

    try:
        issues = await get_open_issues()
    except Exception:
        issues = []

    # Route to a specific named agent if requested
    if agent and agent in _NAMED_AGENTS:
        context = {"tickets": tickets, "issues": issues}
        reply = await _NAMED_AGENTS[agent].run(message, context)
        return {"reply": reply, "action_result": None}

    system_prompt = _build_system_prompt(tickets, issues)

    # Build message list for the API
    messages = [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": message})

    response = await client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
    )

    raw_reply = response.content[0].text

    # Execute any embedded action
    action_result = None
    action = _extract_action(raw_reply)
    if action:
        action_result = await _execute_action(action)

    return {
        "reply": _strip_action_block(raw_reply),
        "action_result": action_result,
    }


async def _execute_action(action: dict) -> dict:
    """Dispatch an action parsed from Claude's response."""
    action_type = action.get("action")

    if action_type == "move_ticket":
        return await move_ticket(
            issue_key=action["issue_key"],
            target_status=action["target_status"],
        )

    if action_type == "create_ticket":
        return await create_ticket(
            summary=action["summary"],
            description=action.get("description", ""),
            priority=action.get("priority", "Medium"),
            story_points=action.get("story_points"),
        )

    if action_type == "fix_issue":
        agent = CodeFixAgent()
        return await agent.fix_issue(
            issue_key=action["issue_key"],
            description=action.get("description", ""),
        )

    return {"error": f"Unknown action type: '{action_type}'"}


async def generate_standup(team_name: str, include_blockers: bool, include_stats: bool) -> str:
    """Generate a standup report from live sprint data."""
    try:
        tickets = await get_sprint_tickets()
    except Exception as e:
        return f"Could not fetch sprint data: {e}"

    in_progress = [t for t in tickets if "progress" in t["status"].lower()]
    done = [t for t in tickets if t["status"].lower() == "done"]
    blocked = [t for t in tickets if t["priority"].lower() in ("highest", "blocker")]

    sections = [f"## Daily Standup — {team_name}\n"]

    if done:
        sections.append("### Done")
        for t in done:
            sections.append(f"- [{t['key']}] {t['summary']} ({t['assignee']})")

    if in_progress:
        sections.append("\n### In Progress")
        for t in in_progress:
            sections.append(f"- [{t['key']}] {t['summary']} ({t['assignee']})")

    if include_blockers and blocked:
        sections.append("\n### Blockers")
        for t in blocked:
            sections.append(f"- [{t['key']}] {t['summary']} — Priority: {t['priority']}")

    if include_stats:
        total = len(tickets)
        done_count = len(done)
        pct = round(done_count / total * 100) if total else 0
        sections.append(f"\n### Stats\n- {done_count}/{total} tickets done ({pct}%)")

    return "\n".join(sections)
