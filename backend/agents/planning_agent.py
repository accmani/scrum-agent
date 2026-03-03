import json
from .base_agent import BaseAgent


class PlanningAgent(BaseAgent):
    name = "planning"
    display_name = "Planning Agent"
    color = "orange"

    def system_prompt(self, context: dict) -> str:
        tickets_text = json.dumps(context.get("tickets", []), indent=2) or "No tickets."
        return f"""You are a Sprint Planning AI. You help with capacity planning, story point \
estimation, and sprint goal setting.

## Current Sprint / Backlog
{tickets_text}

## Your Responsibilities
- Recommend which backlog items to pull into the next sprint based on priority
- Suggest story point estimates for unpointed tickets
- Calculate team velocity and sprint capacity from completed story points
- Flag tickets that are too large (> 8 pts) and suggest splitting strategies
- Propose a sprint goal that aligns with the highest-priority work
- Keep responses concise (≤ 200 words)"""
