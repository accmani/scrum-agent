import json
import re
from .base_agent import BaseAgent
from jira_client import create_ticket, move_ticket


class JiraAgent(BaseAgent):
    name = "jira"
    display_name = "Jira Agent"
    color = "blue"

    def system_prompt(self, context: dict) -> str:
        tickets_text = json.dumps(context.get("tickets", []), indent=2) or "No tickets."
        return f"""You are a Jira specialist AI. You manage the sprint board: creating tickets, \
moving them between statuses, and analysing sprint progress.

## Live Sprint Board
{tickets_text}

## Actions
To take an action embed a JSON block:

Move a ticket:
```action
{{"action": "move_ticket", "issue_key": "PROJ-1", "target_status": "In Progress"}}
```

Create a ticket:
```action
{{"action": "create_ticket", "summary": "Title", "description": "Details", "priority": "Medium", "story_points": 3}}
```

## Guidelines
- Always reference ticket keys (e.g. KAN-42) when discussing issues.
- Only act when the user explicitly requests it.
- After acting, confirm what you did in one sentence.
- Keep responses concise (≤ 150 words)."""

    @staticmethod
    def _extract_action(text: str) -> dict | None:
        match = re.search(r"```action\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                import json as _json
                return _json.loads(match.group(1))
            except Exception:
                return None
        return None

    @staticmethod
    def _strip_action(text: str) -> str:
        return re.sub(r"```action\s*\{.*?\}\s*```", "", text, flags=re.DOTALL).strip()

    async def run(self, message: str, context: dict) -> str:
        raw = await super().run(message, context)
        action = self._extract_action(raw)
        reply = self._strip_action(raw)

        if action:
            result = await self._execute(action)
            reply += f"\n\n*Action result:* `{json.dumps(result)}`"

        return reply

    async def _execute(self, action: dict) -> dict:
        atype = action.get("action")
        if atype == "move_ticket":
            return await move_ticket(
                issue_key=action["issue_key"],
                target_status=action["target_status"],
            )
        if atype == "create_ticket":
            return await create_ticket(
                summary=action["summary"],
                description=action.get("description", ""),
                priority=action.get("priority", "Medium"),
                story_points=action.get("story_points"),
            )
        return {"error": f"Unknown action: {atype}"}
