import { useState, useEffect, useCallback } from 'react'
import Board from './components/Board'
import Chat from './components/Chat'
import Velocity from './components/Velocity'
import Blockers from './components/Blockers'
import Retro from './components/Retro'
import TeamChat from './components/TeamChat'
import Pipeline from './components/Pipeline'
import { fetchJiraTickets, fetchGithubIssues } from './api'

const TABS = [
  { id: 'Board',       icon: '⬜', label: 'Board'       },
  { id: 'Pipeline',    icon: '🤖', label: 'AI Pipeline' },
  { id: 'Team Feed',   icon: '💬', label: 'Team Feed'   },
  { id: 'Velocity',    icon: '📊', label: 'Velocity'    },
  { id: 'Blockers',    icon: '⚠️',  label: 'Blockers'    },
  { id: 'Retro',       icon: '🔄', label: 'Retro'       },
  { id: 'Direct Chat', icon: '🧠', label: 'Direct Chat' },
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
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
          {/* Brand */}
          <div className="flex items-center gap-2.5 flex-shrink-0">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white text-xs font-bold">
              AI
            </div>
            <div>
              <span className="font-semibold text-white text-sm">Enterprise AI Agent</span>
              <span className="ml-2 text-xs text-slate-500 hidden sm:inline">Healthcare Claims Platform</span>
            </div>
            {loading && !tickets.length && (
              <div className="w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin ml-1" />
            )}
          </div>

          {/* Tabs */}
          <nav className="flex gap-0.5 overflow-x-auto">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                  activeTab === tab.id
                    ? tab.id === 'Pipeline'
                      ? 'bg-rose-600 text-white'
                      : 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700'
                }`}
              >
                <span className="leading-none">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>

          {/* Live badge */}
          <div className="flex items-center gap-1.5 text-xs text-slate-500 flex-shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            <span className="hidden sm:inline">{tickets.length} tickets · {issues.length} issues</span>
          </div>
        </div>
      </header>

      {/* ── Main ───────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Initial load spinner — only block non-pipeline tabs */}
        {loading && !tickets.length && activeTab !== 'Pipeline' ? (
          <div className="flex flex-col items-center justify-center h-64 gap-4 text-slate-500">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm">Fetching sprint data…</p>
          </div>
        ) : error && activeTab !== 'Pipeline' ? (
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
            {activeTab === 'Pipeline'    && <Pipeline />}
            {activeTab === 'Team Feed'   && <TeamChat />}
            {activeTab === 'Velocity'    && <Velocity />}
            {activeTab === 'Blockers'    && <Blockers />}
            {activeTab === 'Retro'       && <Retro />}
            {activeTab === 'Direct Chat' && <Chat tickets={tickets} issues={issues} refresh={refresh} />}
          </>
        )}
      </main>
    </div>
  )
}
