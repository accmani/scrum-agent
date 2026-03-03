import { useState, useEffect, useCallback } from 'react'
import Board from './components/Board'
import Chat from './components/Chat'
import Velocity from './components/Velocity'
import Blockers from './components/Blockers'
import Retro from './components/Retro'
import TeamChat from './components/TeamChat'
import { fetchJiraTickets, fetchGithubIssues } from './api'

const TABS = [
  { id: 'Board',       icon: '⬜', label: 'Board' },
  { id: 'Team Feed',   icon: '💬', label: 'Team Feed' },
  { id: 'Velocity',    icon: '📊', label: 'Velocity' },
  { id: 'Blockers',    icon: '⚠️',  label: 'Blockers' },
  { id: 'Retro',       icon: '🔄', label: 'Retro' },
  { id: 'Direct Chat', icon: '🤖', label: 'Direct Chat' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('Board')
  const [tickets, setTickets] = useState([])
  const [issues, setIssues]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [t, i] = await Promise.all([fetchJiraTickets(), fetchGithubIssues()])
      setTickets(t)
      setIssues(i)
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* ── Header ──────────────────────────────────────────── */}
      <header className="bg-slate-800 border-b border-slate-700 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          {/* Brand */}
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white text-xs font-bold">
              S
            </div>
            <span className="font-semibold text-white text-sm">Scrum Agent</span>
            {loading && !tickets.length && (
              <div className="w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin ml-1" />
            )}
          </div>

          {/* Tabs */}
          <nav className="flex gap-1">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700'
                }`}
              >
                <span className="text-base leading-none">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>

          {/* Live badge */}
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            {tickets.length} tickets · {issues.length} issues
          </div>
        </div>
      </header>

      {/* ── Main ───────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Initial load spinner */}
        {loading && !tickets.length ? (
          <div className="flex flex-col items-center justify-center h-64 gap-4 text-slate-500">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm">Fetching sprint data…</p>
          </div>
        ) : error ? (
          <div className="bg-red-900/30 border border-red-700/50 rounded-xl px-5 py-4 text-red-300 text-sm flex items-start gap-3">
            <span className="text-lg leading-none mt-0.5">⚠️</span>
            <div>
              <p className="font-medium mb-1">Failed to load sprint data</p>
              <p className="text-red-400/80">{error}</p>
              <button
                onClick={refresh}
                className="mt-3 text-xs px-3 py-1.5 rounded-md bg-red-800/50 hover:bg-red-700/50 text-red-200 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        ) : (
          <>
            {activeTab === 'Board'       && <Board    tickets={tickets} refresh={refresh} />}
            {activeTab === 'Team Feed'   && <TeamChat />}
            {activeTab === 'Velocity'    && <Velocity />}
            {activeTab === 'Blockers'    && <Blockers />}
            {activeTab === 'Retro'       && <Retro />}
            {activeTab === 'Direct Chat' && <Chat     tickets={tickets} issues={issues} refresh={refresh} />}
          </>
        )}
      </main>
    </div>
  )
}
