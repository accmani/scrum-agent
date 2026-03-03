# Scrum Agent

An AI-powered Scrum assistant that integrates with Jira and GitHub using Claude (Anthropic) to help manage sprints, generate reports, and automate scrum workflows.

## Project Structure

```
scrum-agent/
├── backend/
│   ├── main.py            # FastAPI app + all routes
│   ├── agent.py           # Claude Scrum Master agent
│   ├── jira_client.py     # Jira REST API v3 client
│   ├── github_client.py   # GitHub REST API client
│   ├── models.py          # Pydantic request/response models
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Root layout + tab navigation
│   │   ├── api.js         # Axios API client
│   │   ├── main.jsx       # React entry point
│   │   └── components/
│   │       ├── Board.jsx  # Kanban board with drag-and-drop
│   │       ├── Chat.jsx   # Scrum Agent chat interface
│   │       ├── Standup.jsx# Standup report generator
│   │       └── Stats.jsx  # Sprint statistics dashboard
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── package.json
├── .env                   # Your local credentials (never commit)
├── .env.example           # Credential template
└── README.md
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- A Jira account with API access
- A GitHub account with a personal access token
- An Anthropic API key

## Setup

### 1. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

| Variable            | Where to get it                                                    |
|---------------------|--------------------------------------------------------------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com)            |
| `JIRA_BASE_URL`     | Your Jira instance URL, e.g. `https://acme.atlassian.net`         |
| `JIRA_EMAIL`        | Email address on your Jira/Atlassian account                       |
| `JIRA_API_TOKEN`    | [id.atlassian.com → Security → API tokens](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `JIRA_PROJECT_KEY`  | Found in Jira → Project Settings → Details (e.g. `KAN`, `SCRUM`)  |
| `GITHUB_TOKEN`      | GitHub → Settings → Developer Settings → Personal Access Tokens (`repo` scope) |
| `GITHUB_REPO`       | `owner/repository-name` format                                     |
| `FRONTEND_URL`      | Leave as `http://localhost:5173` for local dev                     |

---

## Running the App

Open **two terminals** from the `scrum-agent/` root:

### Terminal 1 — Backend

```bash
cd backend
python -m venv venv

# macOS / Linux:
source venv/bin/activate

# Windows (PowerShell):
venv\Scripts\Activate.ps1

# Windows (CMD):
venv\Scripts\activate.bat

pip install -r requirements.txt
python main.py
```

API runs at → `http://localhost:8000`
Interactive docs → `http://localhost:8000/docs`

### Terminal 2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at → `http://localhost:5173`

---

## API Routes

| Method | Path                              | Description                         |
|--------|-----------------------------------|-------------------------------------|
| GET    | `/health`                         | Health check                        |
| POST   | `/api/chat`                       | Chat with the Scrum Agent           |
| POST   | `/api/standup`                    | Generate standup report             |
| GET    | `/api/jira/tickets`               | List active sprint tickets          |
| POST   | `/api/jira/tickets`               | Create a new Jira story             |
| PUT    | `/api/jira/tickets/{id}/move`     | Move ticket to a new status         |
| GET    | `/api/jira/stats`                 | Sprint statistics                   |
| GET    | `/api/github/issues`              | List open GitHub issues             |
| POST   | `/api/github/issues`              | Create a new GitHub issue           |

---

## Tech Stack

| Layer        | Technology                        |
|--------------|-----------------------------------|
| AI           | Claude (`claude-sonnet-4-20250514`) via Anthropic SDK |
| Backend      | Python 3.10+, FastAPI, Uvicorn    |
| Frontend     | React 18, Vite, Tailwind CSS      |
| Integrations | Jira REST API v3, GitHub REST API |
| HTTP         | httpx (backend), axios (frontend) |

---

## What You Still Need to Fill In

| Item | Notes |
|------|-------|
| `ANTHROPIC_API_KEY` | Required — the agent won't work without it |
| `JIRA_PROJECT_KEY` | Must match an existing project in your Jira instance |
| `JIRA_API_TOKEN` | Scoped to your account; create one at Atlassian's security page |
| `GITHUB_TOKEN` | Needs `repo` scope to read issues and create/close them |
| `GITHUB_REPO` | Must be a repo you have write access to |
| Jira workflow statuses | The board uses: `Backlog`, `To Do`, `In Progress`, `Review`, `Done`. If your workflow uses different names (e.g. `In Review`, `Selected for Development`), update `mapStatus()` in `Board.jsx` |
| Story points field | Defaults to `customfield_10016`. If your Jira uses a different field ID, update it in `jira_client.py` |
