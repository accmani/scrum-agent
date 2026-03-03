import axios from 'axios'

// Use relative URLs so Vite's proxy forwards them to localhost:8000.
// This avoids CORS preflight requests entirely during development.
const api = axios.create({ baseURL: '' })

// Jira
export const fetchJiraTickets = () =>
  api.get('/api/jira/tickets').then(r => r.data)

export const fetchStats = () =>
  api.get('/api/jira/stats').then(r => r.data)

// Velocity — enriched stats with per-assignee breakdown
export const fetchVelocity = () =>
  api.get('/api/velocity').then(r => r.data)

export const moveTicket = (id, status) =>
  api.put(`/api/jira/tickets/${id}/move`, { status }).then(r => r.data)

export const createTicket = ({ summary, description, priority, story_points }) =>
  api.post('/api/jira/tickets', { summary, description, priority, story_points }).then(r => r.data)

// GitHub
export const fetchGithubIssues = () =>
  api.get('/api/github/issues').then(r => r.data)

// Agent
export const sendChat = (message, history, agent = null) =>
  api.post('/api/chat', { message, history, agent }).then(r => r.data)

export const fixIssue = (issue_key, description = '') =>
  api.post('/api/fix-issue', { issue_key, description }, { timeout: 120000 }).then(r => r.data)

export const sendStandup = ({ team_name, include_blockers, include_stats }) =>
  api.post('/api/standup', { team_name, include_blockers, include_stats }).then(r => r.data)

// Blockers
export const fetchBlockers  = () => api.get('/api/blockers').then(r => r.data)
export const addBlocker     = (text) => api.post('/api/blockers', { text }).then(r => r.data)
export const deleteBlocker  = (id) => api.delete(`/api/blockers/${id}`).then(r => r.data)

// Retro
export const fetchRetro     = () => api.get('/api/retro').then(r => r.data)
export const addRetroItem   = (category, text) => api.post('/api/retro', { category, text }).then(r => r.data)
export const deleteRetroItem= (id) => api.delete(`/api/retro/${id}`).then(r => r.data)
