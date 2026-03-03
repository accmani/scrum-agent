import { useState, useEffect } from 'react'
import { fetchBlockers, addBlocker, deleteBlocker } from '../api'

const PRIORITY_STYLE = {
  Highest: 'bg-red-500/20 text-red-400 ring-1 ring-red-500/30',
  High:    'bg-orange-500/20 text-orange-400 ring-1 ring-orange-500/30',
}

function AutoBlockerCard({ ticket }) {
  return (
    <div className="bg-slate-800 rounded-xl border border-red-700/40 p-4 flex items-start gap-3">
      <span className="text-red-400 text-lg leading-none mt-0.5">⚠</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-mono text-indigo-400">{ticket.key}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${PRIORITY_STYLE[ticket.priority] ?? PRIORITY_STYLE.High}`}>
            {ticket.priority}
          </span>
        </div>
        <p className="text-sm text-slate-200 truncate">{ticket.summary}</p>
        <p className="text-xs text-slate-500 mt-0.5">{ticket.assignee} · {ticket.status}</p>
      </div>
    </div>
  )
}

function ManualBlockerCard({ item, onDelete }) {
  return (
    <div className="bg-slate-800 rounded-xl border border-orange-700/40 p-4 flex items-start gap-3">
      <span className="text-orange-400 text-lg leading-none mt-0.5">🚧</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-200">{item.text}</p>
        <p className="text-xs text-slate-600 mt-1">Added {new Date(item.created_at).toLocaleString()}</p>
      </div>
      <button
        onClick={() => onDelete(item.id)}
        className="text-slate-600 hover:text-red-400 transition-colors text-sm ml-2 flex-shrink-0"
        title="Remove"
      >
        ✕
      </button>
    </div>
  )
}

export default function Blockers() {
  const [data, setData] = useState({ auto: [], manual: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)

  async function load() {
    setLoading(true)
    setError('')
    try { setData(await fetchBlockers()) }
    catch (err) { setError(err.response?.data?.detail ?? err.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleAdd(e) {
    e.preventDefault()
    if (!text.trim()) return
    setSaving(true)
    try {
      await addBlocker(text.trim())
      setText('')
      await load()
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    await deleteBlocker(id)
    await load()
  }

  const totalCount = data.auto.length + data.manual.length

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-white">Blockers</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {totalCount === 0 ? 'No blockers — great!' : `${totalCount} blocker${totalCount !== 1 ? 's' : ''} require attention`}
          </p>
        </div>
        <button onClick={load} className="px-3 py-1.5 text-sm rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors">
          ↻ Refresh
        </button>
      </div>

      {/* Add manual blocker */}
      <form onSubmit={handleAdd} className="flex gap-2 mb-6">
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="Describe a blocker…"
          className="flex-1 bg-slate-800 rounded-lg px-4 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-red-500 border border-slate-700 placeholder:text-slate-600"
        />
        <button
          type="submit"
          disabled={saving || !text.trim()}
          className="px-4 py-2 rounded-lg bg-red-700 hover:bg-red-600 text-white text-sm font-medium disabled:opacity-40 transition-colors"
        >
          {saving ? 'Adding…' : '+ Add Blocker'}
        </button>
      </form>

      {loading ? (
        <div className="flex items-center justify-center h-32 gap-3 text-slate-400">
          <div className="w-5 h-5 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
          Loading blockers…
        </div>
      ) : error ? (
        <div className="bg-red-900/30 border border-red-700/50 rounded-xl px-5 py-4 text-red-300 text-sm">{error}</div>
      ) : totalCount === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 text-slate-600">
          <span className="text-5xl">✅</span>
          <p className="text-sm">No blockers! The sprint is running smoothly.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {data.auto.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-3">
                From Jira — Highest Priority ({data.auto.length})
              </h3>
              <div className="flex flex-col gap-3">
                {data.auto.map(t => <AutoBlockerCard key={t.key} ticket={t} />)}
              </div>
            </div>
          )}
          {data.manual.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-orange-400 uppercase tracking-wider mb-3">
                Manual Blockers ({data.manual.length})
              </h3>
              <div className="flex flex-col gap-3">
                {data.manual.map(m => <ManualBlockerCard key={m.id} item={m} onDelete={handleDelete} />)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
