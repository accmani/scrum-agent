import { useState, useRef } from 'react'
import { moveTicket as apiMoveTicket, createTicket as apiCreateTicket } from '../api'

const COLUMNS = [
  { id: 'Backlog',      color: 'border-slate-600',  dot: 'bg-slate-400' },
  { id: 'To Do',        color: 'border-blue-600',   dot: 'bg-blue-400' },
  { id: 'In Progress',  color: 'border-yellow-500', dot: 'bg-yellow-400' },
  { id: 'Review',       color: 'border-purple-500', dot: 'bg-purple-400' },
  { id: 'Done',         color: 'border-green-600',  dot: 'bg-green-400' },
]

const PRIORITY_STYLE = {
  Highest: 'bg-red-500/20 text-red-400 ring-1 ring-red-500/30',
  High:    'bg-orange-500/20 text-orange-400 ring-1 ring-orange-500/30',
  Medium:  'bg-yellow-500/20 text-yellow-400 ring-1 ring-yellow-500/30',
  Low:     'bg-blue-500/20 text-blue-400 ring-1 ring-blue-500/30',
  Lowest:  'bg-slate-600/50 text-slate-400 ring-1 ring-slate-500/30',
}

function mapStatus(status = '') {
  const s = status.toLowerCase()
  if (s.includes('backlog'))                                          return 'Backlog'
  if (s.includes('progress'))                                         return 'In Progress'
  if (s.includes('review') || s.includes('qa') || s.includes('test')) return 'Review'
  if (s.includes('done') || s.includes('closed') || s.includes('resolved') || s.includes('complete')) return 'Done'
  if (s.includes('todo') || s.includes('to do') || s.includes('selected') || s.includes('open'))      return 'To Do'
  return 'Backlog'
}

const BLANK_FORM = { summary: '', description: '', priority: 'Medium', story_points: '' }

export default function Board({ tickets, refresh }) {
  // Local optimistic state so moves feel instant
  const [localTickets, setLocalTickets] = useState(null)
  const [dragKey, setDragKey] = useState(null)
  const [dragOver, setDragOver] = useState(null)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(BLANK_FORM)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const dragTicket = useRef(null)
  // Track enter/leave depth per column to avoid false dragLeave fires on child elements
  const dragDepth = useRef({})

  const board = localTickets ?? tickets

  const byColumn = Object.fromEntries(COLUMNS.map(c => [c.id, []]))
  for (const t of board) {
    const col = mapStatus(t.status)
    byColumn[col].push(t)
  }

  // ── Drag handlers ────────────────────────────────────────────
  function onDragStart(e, ticket) {
    dragTicket.current = ticket
    setDragKey(ticket.key)
    e.dataTransfer.effectAllowed = 'move'
  }

  function onDragEnter(e, colId) {
    e.preventDefault()
    dragDepth.current[colId] = (dragDepth.current[colId] ?? 0) + 1
    setDragOver(colId)
  }

  function onDragOver(e, colId) {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }

  function onDragLeave(e, colId) {
    dragDepth.current[colId] = (dragDepth.current[colId] ?? 1) - 1
    if (dragDepth.current[colId] <= 0) {
      dragDepth.current[colId] = 0
      setDragOver(null)
    }
  }

  async function onDrop(e, colId) {
    e.preventDefault()
    dragDepth.current[colId] = 0
    setDragOver(null)
    const ticket = dragTicket.current
    if (!ticket || mapStatus(ticket.status) === colId) return

    // Optimistic update
    setLocalTickets(board.map(t =>
      t.key === ticket.key ? { ...t, status: colId } : t,
    ))
    setDragKey(null)

    try {
      await apiMoveTicket(ticket.key, colId)
      await refresh()
      setLocalTickets(null)
    } catch {
      setLocalTickets(null) // revert
    }
  }

  // ── Create ticket ─────────────────────────────────────────────
  async function handleCreate(e) {
    e.preventDefault()
    if (!form.summary.trim()) return
    setSaving(true)
    setError('')
    try {
      await apiCreateTicket({
        summary: form.summary.trim(),
        description: form.description.trim(),
        priority: form.priority,
        story_points: form.story_points ? Number(form.story_points) : null,
      })
      setForm(BLANK_FORM)
      setShowModal(false)
      await refresh()
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to create ticket')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-white">Sprint Board</h2>
        <div className="flex gap-2">
          <button
            onClick={refresh}
            className="px-3 py-1.5 text-sm rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
          >
            ↻ Refresh
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="px-3 py-1.5 text-sm rounded-md bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
          >
            + Add Ticket
          </button>
        </div>
      </div>

      {/* Columns */}
      <div className="grid grid-cols-5 gap-3 items-start">
        {COLUMNS.map(col => (
          <div
            key={col.id}
            onDragEnter={e => onDragEnter(e, col.id)}
            onDragOver={e => onDragOver(e, col.id)}
            onDragLeave={e => onDragLeave(e, col.id)}
            onDrop={e => onDrop(e, col.id)}
            className={`rounded-xl border-t-2 ${col.color} bg-slate-800/50 p-3 min-h-[60vh] transition-colors ${
              dragOver === col.id ? 'bg-slate-700/60 ring-1 ring-indigo-500' : ''
            }`}
          >
            {/* Column header */}
            <div className="flex items-center gap-2 mb-3">
              <span className={`w-2 h-2 rounded-full ${col.dot}`} />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                {col.id}
              </span>
              <span className="ml-auto text-xs text-slate-500 bg-slate-700 rounded-full px-1.5 py-0.5">
                {byColumn[col.id].length}
              </span>
            </div>

            {/* Cards */}
            <div className="flex flex-col gap-2">
              {byColumn[col.id].map(ticket => (
                <div
                  key={ticket.key}
                  draggable
                  onDragStart={e => onDragStart(e, ticket)}
                  className={`bg-slate-800 rounded-lg p-3 cursor-grab active:cursor-grabbing border border-slate-700 hover:border-slate-500 transition-all ${
                    dragKey === ticket.key ? 'opacity-40 scale-95' : ''
                  }`}
                >
                  {/* Key + points */}
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-mono text-indigo-400">{ticket.key}</span>
                    {ticket.story_points != null && (
                      <span className="text-xs bg-slate-700 text-slate-300 rounded-full px-1.5 py-0.5">
                        {ticket.story_points} pts
                      </span>
                    )}
                  </div>

                  {/* Summary */}
                  <p className="text-sm text-slate-200 leading-snug mb-2 line-clamp-2">
                    {ticket.summary}
                  </p>

                  {/* Priority + assignee */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                      PRIORITY_STYLE[ticket.priority] ?? PRIORITY_STYLE.Medium
                    }`}>
                      {ticket.priority}
                    </span>
                    <span className="text-[10px] text-slate-500 ml-auto truncate max-w-[80px]">
                      {ticket.assignee}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Create Ticket Modal */}
      {showModal && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={e => e.target === e.currentTarget && setShowModal(false)}
        >
          <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-md p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-white mb-4">Create Jira Ticket</h3>
            <form onSubmit={handleCreate} className="flex flex-col gap-3">
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Summary *</label>
                <input
                  value={form.summary}
                  onChange={e => setForm(f => ({ ...f, summary: e.target.value }))}
                  placeholder="Short description of the ticket"
                  className="w-full bg-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-500"
                  required
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Description</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  rows={3}
                  placeholder="More details..."
                  className="w-full bg-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-500 resize-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Priority</label>
                  <select
                    value={form.priority}
                    onChange={e => setForm(f => ({ ...f, priority: e.target.value }))}
                    className="w-full bg-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    {['Highest', 'High', 'Medium', 'Low', 'Lowest'].map(p => (
                      <option key={p}>{p}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Story Points</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={form.story_points}
                    onChange={e => setForm(f => ({ ...f, story_points: e.target.value }))}
                    placeholder="e.g. 3"
                    className="w-full bg-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-500"
                  />
                </div>
              </div>

              {error && <p className="text-sm text-red-400">{error}</p>}

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => { setShowModal(false); setForm(BLANK_FORM); setError('') }}
                  className="flex-1 px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium disabled:opacity-50 transition-colors"
                >
                  {saving ? 'Creating…' : 'Create Ticket'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
