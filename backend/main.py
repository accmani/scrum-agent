import os
from dotenv import load_dotenv

# Load .env FIRST — before any local module runs module-level os.getenv() calls
load_dotenv(override=True)

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from models import (
    ChatRequest,
    StandupRequest,
    CreateTicketRequest,
    MoveTicketRequest,
    CreateGithubIssueRequest,
)
from agent import run_agent, generate_standup
from jira_client import (
    get_sprint_tickets,
    create_ticket,
    move_ticket as jira_move_ticket,
    get_sprint_stats,
)
from github_client import get_open_issues, create_issue
from orchestrator import handle_team_chat
from routers import blockers, retro, velocity
import database

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    yield


app = FastAPI(title="Scrum Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(blockers.router)
app.include_router(retro.router)
app.include_router(velocity.router)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@app.post("/api/chat", tags=["Agent"])
async def chat(req: ChatRequest):
    try:
        result = await run_agent(message=req.message, history=req.history, agent=req.agent)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Standup
# ---------------------------------------------------------------------------

@app.post("/api/standup", tags=["Agent"])
async def standup(req: StandupRequest):
    try:
        report = await generate_standup(
            team_name=req.team_name,
            include_blockers=req.include_blockers,
            include_stats=req.include_stats,
        )
        return {"report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Jira
# ---------------------------------------------------------------------------

@app.get("/api/jira/tickets", tags=["Jira"])
async def list_tickets():
    try:
        return await get_sprint_tickets()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/jira/tickets", tags=["Jira"], status_code=201)
async def new_ticket(req: CreateTicketRequest):
    try:
        return await create_ticket(
            summary=req.summary,
            description=req.description,
            priority=req.priority,
            story_points=req.story_points,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.put("/api/jira/tickets/{ticket_id}/move", tags=["Jira"])
async def move_ticket_route(ticket_id: str, req: MoveTicketRequest):
    try:
        return await jira_move_ticket(issue_key=ticket_id, target_status=req.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/jira/stats", tags=["Jira"])
async def sprint_stats():
    try:
        return await get_sprint_stats()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

@app.get("/api/github/issues", tags=["GitHub"])
async def list_issues():
    try:
        return await get_open_issues()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/github/issues", tags=["GitHub"], status_code=201)
async def new_issue(req: CreateGithubIssueRequest):
    try:
        return await create_issue(title=req.title, body=req.body, labels=req.labels)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# Team Feed WebSocket  (two paths: short alias + full)
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def team_feed_ws(websocket: WebSocket):
    await handle_team_chat(websocket)


@app.websocket("/ws/team-chat")
async def team_feed_ws_compat(websocket: WebSocket):
    await handle_team_chat(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
