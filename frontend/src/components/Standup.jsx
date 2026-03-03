import { useState } from 'react'
import { sendStandup } from '../api'

export default function Standup() {
  const [form, setForm] = useState({
    team_name: 'Engineering',
    include_blockers: true,
    include_stats: true,
  })
  const [report, setReport] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setReport('')
    try {
      const data = await sendStandup(form)
      setReport(data.report)
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-lg font-semibold text-white mb-5">Daily Standup</h2>

      <form onSubmit={handleSubmit} className="bg-slate-800 rounded-xl border border-slate-700 p-6 flex flex-col gap-4">
        {/* Team name */}
        <div>
          <label className="text-xs font-medium text-slate-400 mb-1.5 block uppercase tracking-wider">
            Team Name
          </label>
          <input
            value={form.team_name}
            onChange={e => setForm(f => ({ ...f, team_name: e.target.value }))}
            placeholder="e.g. Engineering"
            className="w-full bg-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-500"
          />
        </div>

        {/* Toggles */}
        <div className="flex gap-6">
          {[
            { key: 'include_blockers', label: 'Include Blockers' },
            { key: 'include_stats',   label: 'Include Stats' },
          ].map(({ key, label }) => (
            <label key={key} className="flex items-center gap-2.5 cursor-pointer group">
              <div
                onClick={() => setForm(f => ({ ...f, [key]: !f[key] }))}
                className={`w-9 h-5 rounded-full transition-colors relative ${
                  form[key] ? 'bg-indigo-600' : 'bg-slate-600'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                    form[key] ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </div>
              <span className="text-sm text-slate-300 group-hover:text-white transition-colors">{label}</span>
            </label>
          ))}
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-700/50 rounded-lg px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Generating report…
            </>
          ) : (
            'Generate Standup Report'
          )}
        </button>
      </form>

      {/* Report Output */}
      {report && (
        <div className="mt-6 bg-slate-800 rounded-xl border border-slate-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">Generated Report</h3>
            <button
              onClick={() => navigator.clipboard?.writeText(report)}
              className="text-xs px-2.5 py-1 rounded bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors"
            >
              Copy
            </button>
          </div>
          <div className="prose prose-sm prose-invert max-w-none">
            {report.split('\n').map((line, i) => {
              if (line.startsWith('### ')) {
                return (
                  <h4 key={i} className="text-indigo-400 font-semibold text-sm mt-4 mb-1.5">
                    {line.replace('### ', '')}
                  </h4>
                )
              }
              if (line.startsWith('## ')) {
                return (
                  <h3 key={i} className="text-white font-bold text-base mt-0 mb-3 pb-2 border-b border-slate-700">
                    {line.replace('## ', '')}
                  </h3>
                )
              }
              if (line.startsWith('- ')) {
                return (
                  <div key={i} className="flex gap-2 text-sm text-slate-300 py-0.5">
                    <span className="text-indigo-400 shrink-0">•</span>
                    <span>{line.replace('- ', '')}</span>
                  </div>
                )
              }
              return line ? (
                <p key={i} className="text-sm text-slate-300">{line}</p>
              ) : (
                <div key={i} className="h-1" />
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
