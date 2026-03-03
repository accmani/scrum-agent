from pydantic import BaseModel, Field
from typing import Literal


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    # Optional: restrict reply to one agent ("scrum_master", "jira", "github", "standup", "planning")
    # None / missing → original single-prompt agent (backward-compatible)
    agent: str | None = None


class BlockerCreate(BaseModel):
    text: str


class RetroItemCreate(BaseModel):
    category: Literal["well", "improve", "action"]
    text: str


class StandupRequest(BaseModel):
    team_name: str = "Engineering"
    include_blockers: bool = True
    include_stats: bool = True


class CreateTicketRequest(BaseModel):
    summary: str
    description: str = ""
    priority: Literal["Highest", "High", "Medium", "Low", "Lowest"] = "Medium"
    story_points: int | None = None


class MoveTicketRequest(BaseModel):
    status: str  # Human-readable target status, e.g. "In Progress", "Done"


class CreateGithubIssueRequest(BaseModel):
    title: str
    body: str = ""
    labels: list[str] | None = None
