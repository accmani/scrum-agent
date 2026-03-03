import { useState, useEffect } from 'react'
import { fetchStats } from '../api'

const STATUS_COLOR = {
  'Backlog':     'bg-slate-500',
  'To Do':       'bg-blue-500',
  'In Progress': 'bg-yellow-500',
  'Review':      'bg-purple-500',
  'Done':        'bg-green-500',
}

function StatCard({ label, value, sub, accent }) {
  return (
    <div className={`bg-slate-800 rounded-xl border border-slate-700 p-5 flex flex-col gap-1`}>
      <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</span>
      <span className={`text-3xl font-bold ${accent ?? 'text-white'}`}>{value ?? '—'}</span>
      {sub && <span className="text-xs text-slate-500">{sub}</span>}
    </div>
  )
}

function BarChart({ data, total }) {
  if (!total) return <p className="text-sm text-slate-500">No data</p>
  return (
    <div className="flex flex-col gap-2.5">
      {Object.entries(data).map(([status, count]) => {
        const pct = Math.round((count / total) * 100)
        const color = STATUS_COLOR[status] ?? 'bg-slate-500'
        return (
          <div key={status} className="flex items-center gap-3">
            <span className="text-xs text-slate-400 w-24 shrink-0 truncate">{status}</span>
            <div className="flex-1 bg-slate-700 rounded-full h-2.5 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${color}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs text-slate-400 w-12 text-right shrink-0">
              {count} <span className="text-slate-600">({pct}%)</span>
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function Stats() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      setStats(await fetchStats())
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 gap-3 text-slate-400">
        <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        Loading stats…
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-900/30 border border-red-700/50 rounded-xl px-5 py-4 text-red-300 text-sm">
        {error}
      </div>
    )
  }

  const byStatus = stats?.tickets_by_status ?? {}
  const inProgress = byStatus['In Progress'] ?? 0
  const highPriority = stats?.blockers_count ?? 0
  const remaining = (stats?.total_points ?? 0) - (stats?.done_points ?? 0)

  const cards = [
    {
      label: 'Tickets Done',
      value: `${byStatus['Done'] ?? 0} / ${stats?.total_tickets ?? 0}`,
      sub: 'tickets completed this sprint',
      accent: 'text-green-400',
    },
    {
      label: 'Story Points Done',
      value: stats?.done_points ?? 0,
      sub: `of ${stats?.total_points ?? 0} total points`,
      accent: 'text-blue-400',
    },
    {
      label: 'Completion',
      value: `${stats?.completion_pct ?? 0}%`,
      sub: 'sprint velocity',
      accent: stats?.completion_pct >= 75 ? 'text-green-400' : stats?.completion_pct >= 40 ? 'text-yellow-400' : 'text-red-400',
    },
    {
      label: 'In Progress',
      value: inProgress,
      sub: 'tickets actively worked on',
      accent: 'text-yellow-400',
    },
    {
      label: 'High Priority Open',
      value: highPriority,
      sub: 'Highest / blocker tickets',
      accent: highPriority > 0 ? 'text-red-400' : 'text-slate-300',
    },
    {
      label: 'Points Remaining',
      value: remaining,
      sub: 'story points left to complete',
      accent: 'text-purple-400',
    },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-white">Sprint Dashboard</h2>
        <button
          onClick={load}
          className="px-3 py-1.5 text-sm rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {cards.map(c => <StatCard key={c.label} {...c} />)}
      </div>

      {/* Bar Chart */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
        <h3 className="text-sm font-semibold text-white mb-5">Ticket Distribution by Status</h3>
        <BarChart data={byStatus} total={stats?.total_tickets ?? 0} />
      </div>
    </div>
  )
}
