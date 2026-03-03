import os
import anthropic

MODEL = "claude-sonnet-4-20250514"

# Shared AsyncAnthropic client — initialized once at import time.
# main.py calls load_dotenv(override=True) before any local imports,
# so os.environ["ANTHROPIC_API_KEY"] is always the .env value.
_anthropic_client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


class BaseAgent:
    """Abstract base for all specialized Scrum agents."""

    #: Short identifier used in WebSocket messages and UI labels
    name: str = "base"
    #: Human-readable label shown in the Team Chat panel
    display_name: str = "Agent"
    #: Tailwind color token (without the bg- prefix) for the avatar bubble
    color: str = "slate"

    def __init__(self) -> None:
        self._client = _anthropic_client

    def system_prompt(self, context: dict) -> str:
        """Return the system prompt. Subclasses must override."""
        raise NotImplementedError

    async def run(self, message: str, context: dict) -> str:
        """
        Send *message* to Claude with the agent's system prompt and context.
        Returns the assistant's plain-text reply.
        """
        response = await self._client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=self.system_prompt(context),
            messages=[{"role": "user", "content": message}],
        )
        return response.content[0].text
