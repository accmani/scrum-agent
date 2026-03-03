import { useState, useEffect } from 'react'
import { fetchVelocity } from '../api'

const STATUS_COLOR = {
  Backlog:      'bg-slate-500',
  'To Do':      'bg-blue-500',
  'In Progress':'bg-yellow-500',
  Review:       'bg-purple-500',
  Done:         'bg-green-500',
}

function StatCard({ label, value, sub, accent }) {
  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 p-5 flex flex-col gap-1">
      <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</span>
      <span className={`text-3xl font-bold ${accent ?? 'text-white'}`}>{value ?? '—'}</span>
      {sub && <span className="text-xs text-slate-500">{sub}</span>}
    </div>
  )
}

function BurndownBar({ done, total }) {
  const pct = total ? Math.round((done / total) * 100) : 0
  const color = pct >= 75 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-400 mb-2">
        <span>Sprint Burndown</span>
        <span>{done} / {total} pts ({pct}%)</span>
      </div>
      <div className="w-full bg-slate-700 rounded-full h-4 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function DistributionChart({ data, total }) {
  if (!total) return <p className="text-sm text-slate-500">No data</p>
  return (
    <div className="flex flex-col gap-2.5">
      {Object.entries(data).map(([status, count]) => {
        const pct = Math.round((count / total) * 100)
        const color = STATUS_COLOR[status] ?? 'bg-slate-500'
        return (
          <div key={status} className="flex items-center gap-3">
            <span className="text-xs text-slate-400 w-24 shrink-0">{status}</span>
            <div className="flex-1 bg-slate-700 rounded-full h-2.5 overflow-hidden">
              <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-xs text-slate-400 w-16 text-right shrink-0">
              {count} <span className="text-slate-600">({pct}%)</span>
            </span>
          </div>
        )
      })}
    </div>
  )
}

function AssigneeTable({ rows }) {
  if (!rows || rows.length === 0) {
    return <p className="text-sm text-slate-500">No assignee data</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-slate-500 uppercase tracking-wider border-b border-slate-700">
            <th className="pb-2 pr-4 font-medium">Assignee</th>
            <th className="pb-2 pr-4 font-medium text-right">Tickets</th>
            <th className="pb-2 pr-4 font-medium text-right">Done</th>
            <th className="pb-2 pr-4 font-medium text-right">Points</th>
            <th className="pb-2 font-medium text-right">Pts Done</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700/50">
          {rows.map(r => {
            const donePct = r.tickets ? Math.round((r.done / r.tickets) * 100) : 0
            return (
              <tr key={r.assignee} className="text-slate-300">
                <td className="py-2.5 pr-4 font-medium text-slate-200 truncate max-w-[140px]">{r.assignee}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{r.tickets}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">
                  <span className="text-green-400">{r.done}</span>
                  <span className="text-slate-600 text-xs ml-1">({donePct}%)</span>
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-blue-400">{r.points}</td>
                <td className="py-2.5 text-right tabular-nums text-green-400">{r.done_points}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function Velocity() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try { setData(await fetchVelocity()) }
    catch (err) { setError(err.response?.data?.detail ?? err.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-48 gap-3 text-slate-400">
      <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      Loading velocity data…
    </div>
  )

  if (error) return (
    <div className="bg-red-900/30 border border-red-700/50 rounded-xl px-5 py-4 text-red-300 text-sm">{error}</div>
  )

  const byStatus  = data?.tickets_by_status ?? {}
  const remaining = (data?.total_points ?? 0) - (data?.done_points ?? 0)
  const inProgress = byStatus['In Progress'] ?? 0

  const cards = [
    {
      label: 'Velocity',
      value: `${data?.completion_pct ?? 0}%`,
      sub: 'story points done / total',
      accent: data?.completion_pct >= 75 ? 'text-green-400' : data?.completion_pct >= 40 ? 'text-yellow-400' : 'text-red-400',
    },
    {
      label: 'Points Done',
      value: data?.done_points ?? 0,
      sub: `of ${data?.total_points ?? 0} total`,
      accent: 'text-blue-400',
    },
    {
      label: 'Tickets Done',
      value: `${byStatus['Done'] ?? 0} / ${data?.total_tickets ?? 0}`,
      sub: 'completed this sprint',
      accent: 'text-green-400',
    },
    {
      label: 'In Progress',
      value: inProgress,
      sub: 'actively worked on',
      accent: 'text-yellow-400',
    },
    {
      label: 'Points Remaining',
      value: remaining,
      sub: 'left to complete',
      accent: 'text-purple-400',
    },
    {
      label: 'Blockers',
      value: data?.blockers_count ?? 0,
      sub: 'Highest / blocker priority',
      accent: (data?.blockers_count ?? 0) > 0 ? 'text-red-400' : 'text-slate-300',
    },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-white">Velocity</h2>
        <button
          onClick={load}
          className="px-3 py-1.5 text-sm rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Burndown bar */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 mb-6">
        <BurndownBar done={data?.done_points ?? 0} total={data?.total_points ?? 0} />
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {cards.map(c => <StatCard key={c.label} {...c} />)}
      </div>

      {/* Two-column bottom row */}
      <div className="grid grid-cols-2 gap-4">
        {/* Status distribution */}
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
          <h3 className="text-sm font-semibold text-white mb-5">Ticket Distribution</h3>
          <DistributionChart data={byStatus} total={data?.total_tickets ?? 0} />
        </div>

        {/* Per-assignee breakdown — live from /api/velocity */}
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
          <h3 className="text-sm font-semibold text-white mb-5">Assignee Breakdown</h3>
          <AssigneeTable rows={data?.assignee_breakdown ?? []} />
        </div>
      </div>
    </div>
  )
}
