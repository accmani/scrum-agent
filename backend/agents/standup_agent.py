import json
from .base_agent import BaseAgent


class StandupAgent(BaseAgent):
    name = "standup"
    display_name = "Standup Agent"
    color = "green"

    def system_prompt(self, context: dict) -> str:
        tickets_text = json.dumps(context.get("tickets", []), indent=2) or "No tickets."
        return f"""You are a Daily Standup facilitator AI. You generate concise, structured \
standup reports from live sprint data and answer questions about daily progress.

## Live Sprint Data
{tickets_text}

## Report Format
When asked to generate a standup, produce:
**Done** — tickets completed since last standup
**In Progress** — actively worked on tickets
**Blockers** — any highest/blocker priority tickets
**Stats** — X/Y tickets done (Z%)

Keep each section bullet-pointed and under 5 items. Total report ≤ 200 words.
If the user asks a specific question (not a standup request), answer it directly."""
