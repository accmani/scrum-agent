import { useState, useEffect } from 'react'
import { fetchRetro, addRetroItem, deleteRetroItem } from '../api'

const COLUMNS = [
  { id: 'well',    label: 'Went Well',   emoji: '✅', color: 'border-green-600',  dot: 'bg-green-400',  accent: 'text-green-400' },
  { id: 'improve', label: 'To Improve',  emoji: '🔧', color: 'border-yellow-500', dot: 'bg-yellow-400', accent: 'text-yellow-400' },
  { id: 'action',  label: 'Action Items',emoji: '🎯', color: 'border-blue-500',   dot: 'bg-blue-400',   accent: 'text-blue-400' },
]

function RetroCard({ item, onDelete }) {
  return (
    <div className="bg-slate-700/60 rounded-lg px-3 py-2.5 flex items-start gap-2 group">
      <p className="flex-1 text-sm text-slate-200 leading-snug">{item.text}</p>
      <button
        onClick={() => onDelete(item.id)}
        className="text-slate-600 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100 text-xs flex-shrink-0 mt-0.5"
        title="Remove"
      >
        ✕
      </button>
    </div>
  )
}

function AddForm({ category, onAdd }) {
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!text.trim()) return
    setSaving(true)
    try {
      await onAdd(category, text.trim())
      setText('')
    } finally {
      setSaving(false)
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-2 flex gap-1.5">
      <input
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Add item…"
        className="flex-1 bg-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 outline-none focus:ring-1 focus:ring-indigo-500 placeholder:text-slate-600"
      />
      <button
        type="submit"
        disabled={saving || !text.trim()}
        className="px-2.5 py-1.5 rounded-lg bg-slate-600 hover:bg-slate-500 text-white text-xs disabled:opacity-40 transition-colors"
      >
        +
      </button>
    </form>
  )
}

export default function Retro() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await fetchRetro()
      setItems(data.items ?? [])
    }
    catch (err) { setError(err.response?.data?.detail ?? err.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleAdd(category, text) {
    await addRetroItem(category, text)
    await load()
  }

  async function handleDelete(id) {
    await deleteRetroItem(id)
    await load()
  }

  const byCategory = Object.fromEntries(COLUMNS.map(c => [c.id, []]))
  for (const item of items) {
    if (byCategory[item.category]) byCategory[item.category].push(item)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-white">Retrospective</h2>
          <p className="text-xs text-slate-500 mt-0.5">{items.length} item{items.length !== 1 ? 's' : ''} · stored for this session</p>
        </div>
        <button onClick={load} className="px-3 py-1.5 text-sm rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors">
          ↻ Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32 gap-3 text-slate-400">
          <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          Loading retro board…
        </div>
      ) : error ? (
        <div className="bg-red-900/30 border border-red-700/50 rounded-xl px-5 py-4 text-red-300 text-sm">{error}</div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {COLUMNS.map(col => (
            <div
              key={col.id}
              className={`rounded-xl border-t-2 ${col.color} bg-slate-800/50 p-4 min-h-[60vh]`}
            >
              {/* Column header */}
              <div className="flex items-center gap-2 mb-4">
                <span>{col.emoji}</span>
                <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">{col.label}</span>
                <span className="ml-auto text-xs text-slate-500 bg-slate-700 rounded-full px-1.5 py-0.5">
                  {byCategory[col.id].length}
                </span>
              </div>

              {/* Items */}
              <div className="flex flex-col gap-2">
                {byCategory[col.id].map(item => (
                  <RetroCard key={item.id} item={item} onDelete={handleDelete} />
                ))}
              </div>

              {/* Add form */}
              <AddForm category={col.id} onAdd={handleAdd} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
