import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'

const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/pipeline`

// Step metadata — maps step key → icon + colour
const STEP_META = {
  analyzing:         { icon: '🔍', label: 'Analyzing Issue',         agent: 'Scrum Master' },
  discovering_files: { icon: '📁', label: 'Scanning Repository',     agent: 'Code Fix'     },
  reading_code:      { icon: '📖', label: 'Reading Source Code',      agent: 'Code Fix'     },
  generating_fix:    { icon: '🔧', label: 'Generating Code Fix',      agent: 'Code Fix'     },
  reviewing:         { icon: '👁',  label: 'Peer Code Review',         agent: 'Code Reviewer'},
  generating_tests:  { icon: '🧪', label: 'Writing Unit Tests',       agent: 'Test Agent'   },
  creating_branch:   { icon: '🌿', label: 'Creating Feature Branch',  agent: 'Code Fix'     },
  committing:        { icon: '💾', label: 'Committing Changes',       agent: 'Code Fix'     },
  creating_pr:       { icon: '📬', label: 'Opening Pull Request',     agent: 'Code Fix'     },
  moving_ticket:     { icon: '🎯', label: 'Updating Jira Ticket',     agent: 'Jira'         },
  complete:          { icon: '✅', label: 'Pipeline Complete',         agent: ''             },
}

const AGENT_COLORS = {
  scrum_master:  'bg-indigo-600',
  code_fix:      'bg-rose-600',
  code_reviewer: 'bg-amber-500',
  test:          'bg-cyan-600',
  jira:          'bg-blue-600',
}

function StepRow({ step }) {
  const meta = STEP_META[step.step] || { icon: '⚙️', label: step.label, agent: '' }
  const status = step.status

  return (
    <div className="flex items-center gap-3 py-2">
      {/* Status indicator */}
      <div className="w-6 flex-shrink-0 flex items-center justify-center">
        {status === 'complete'    && <span className="text-green-400 text-base">✓</span>}
        {status === 'in_progress' && (
          <div className="w-4 h-4 border-2 border-rose-400 border-t-transparent rounded-full animate-spin" />
        )}
        {status === 'pending'     && <span className="text-slate-600 text-base">○</span>}
        {status === 'error'       && <span className="text-red-400 text-base">✗</span>}
      </div>

      {/* Icon + label */}
      <span className="text-base w-6 flex-shrink-0">{meta.icon}</span>
      <div className="flex-1 min-w-0">
        <span className={`text-sm font-medium ${
          status === 'complete'    ? 'text-slate-200' :
          status === 'in_progress' ? 'text-white'     :
          status === 'error'       ? 'text-red-400'   :
          'text-slate-500'
        }`}>
          {step.label || meta.label}
        </span>
        {meta.agent && (
          <span className="ml-2 text-xs text-slate-500">· {meta.agent}</span>
        )}
      </div>

      {/* Timing */}
      {step.started_at && (
        <span className="text-[10px] text-slate-600 flex-shrink-0">
          {new Date(step.started_at).toLocaleTimeString()}
        </span>
      )}
    </div>
  )
}

function RunCard({ run, isActive }) {
  const [expanded, setExpanded] = useState(isActive)

  useEffect(() => {
    if (isActive) setExpanded(true)
  }, [isActive])

  const statusColor =
    run.status === 'complete' ? 'border-green-700/50 bg-green-900/10' :
    run.status === 'error'    ? 'border-red-700/50 bg-red-900/10'     :
    'border-rose-700/40 bg-rose-900/5'

  const statusLabel =
    run.status === 'complete' ? '✅ Complete'   :
    run.status === 'error'    ? '❌ Failed'     :
    '⚙️ Running…'

  const elapsed = run.completed_at && run.started_at
    ? Math.round((new Date(run.completed_at) - new Date(run.started_at)) / 1000)
    : null

  return (
    <div className={`border rounded-xl overflow-hidden ${statusColor}`}>
      {/* Header */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-xs font-mono text-slate-500 flex-shrink-0">#{run.run_id}</span>
          <div className="min-w-0">
            <span className="text-sm font-semibold text-white truncate block">{run.issue_title}</span>
            <span className="text-xs text-slate-400">{run.issue_key}</span>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0 ml-3">
          {elapsed && <span className="text-xs text-slate-500">{elapsed}s</span>}
          <span className="text-xs text-slate-300">{statusLabel}</span>
          <span className="text-slate-500 text-xs">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {/* Steps */}
      {expanded && (
        <div className="px-4 pb-3 border-t border-white/5">
          <div className="mt-2 space-y-0">
            {run.steps.map((step, i) => <StepRow key={i} step={step} />)}
            {run.status === 'running' && run.steps.length === 0 && (
              <p className="text-xs text-slate-500 py-2">Starting pipeline…</p>
            )}
          </div>

          {/* Result */}
          {run.result && (
            <div className="mt-3 p-3 rounded-lg bg-green-900/20 border border-green-700/30 space-y-1.5">
              <p className="text-xs font-semibold text-green-300">Pull Request Created</p>
              {run.result.jira_key && (
                <p className="text-xs text-green-400">
                  Jira <span className="font-mono">{run.result.jira_key}</span> → In Review
                </p>
              )}
              {run.result.branch && (
                <p className="text-xs text-green-400">
                  Branch: <span className="font-mono">{run.result.branch}</span>
                </p>
              )}
              {run.result.files_changed?.length > 0 && (
                <p className="text-xs text-green-400">
                  Files: {run.result.files_changed.map(f => (
                    <span key={f} className="font-mono bg-green-900/40 px-1 rounded mr-1">{f.split('/').pop()}</span>
                  ))}
                </p>
              )}
              {run.result.tests_generated > 0 && (
                <p className="text-xs text-green-400">
                  Tests generated: {run.result.tests_generated} file(s)
                </p>
              )}
              {run.result.review_verdict && (
                <p className="text-xs text-green-400">
                  Review: <span className="font-semibold">{run.result.review_verdict}</span>
                  {run.result.review_summary && ` — ${run.result.review_summary}`}
                </p>
              )}
              {run.result.pr_url && (
                <a
                  href={run.result.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-green-300 underline hover:text-green-200 mt-1"
                >
                  View PR #{run.result.pr_number} →
                </a>
              )}
            </div>
          )}

          {run.error && (
            <div className="mt-3 p-3 rounded-lg bg-red-900/20 border border-red-700/30">
              <p className="text-xs font-semibold text-red-300 mb-1">Pipeline Error</p>
              <p className="text-xs text-red-400">{run.error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Pipeline() {
  const [runs, setRuns] = useState([])
  const [connected, setConnected] = useState(false)
  const [issueKey, setIssueKey] = useState('')
  const [issueDesc, setIssueDesc] = useState('')
  const [triggering, setTriggering] = useState(false)
  const [triggerMsg, setTriggerMsg] = useState('')
  const wsRef = useRef(null)

  // ── Update a run by run_id (or add it) ──────────────────────────────────
  const upsertRun = useCallback((runId, updater) => {
    setRuns(prev => {
      const idx = prev.findIndex(r => r.run_id === runId)
      if (idx === -1) return prev
      const updated = [...prev]
      updated[idx] = updater(updated[idx])
      return updated
    })
  }, [])

  // ── WebSocket ─────────────────────────────────────────────────────────────
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen  = () => setConnected(true)
    ws.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
    ws.onerror = () => ws.close()

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)

      if (msg.type === 'pipeline_history') {
        setRuns(msg.runs || [])
      }

      if (msg.type === 'pipeline_start') {
        setRuns(prev => [{
          run_id:      msg.run_id,
          issue_key:   msg.issue_key,
          issue_title: msg.issue_title,
          status:      'running',
          steps:       [],
          result:      null,
          error:       null,
          started_at:  new Date().toISOString(),
          completed_at: null,
        }, ...prev])
      }

      if (msg.type === 'pipeline_step') {
        upsertRun(msg.run_id, run => {
          const steps = [...run.steps]
          const idx = steps.findIndex(s => s.step === msg.step)
          if (idx === -1) {
            steps.push({ step: msg.step, label: msg.label, agent: msg.agent, status: msg.status, started_at: new Date().toISOString() })
          } else {
            steps[idx] = { ...steps[idx], status: msg.status }
          }
          return { ...run, steps }
        })
      }

      if (msg.type === 'pipeline_complete') {
        upsertRun(msg.run_id, run => ({
          ...run,
          status:       'complete',
          result:       msg.result,
          completed_at: new Date().toISOString(),
        }))
      }

      if (msg.type === 'pipeline_error') {
        upsertRun(msg.run_id, run => ({
          ...run,
          status:       'error',
          error:        msg.error,
          completed_at: new Date().toISOString(),
        }))
      }
    }
  }, [upsertRun])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  // ── Manual trigger ────────────────────────────────────────────────────────
  async function handleTrigger(e) {
    e.preventDefault()
    const key = issueKey.trim()
    if (!key) return
    setTriggering(true)
    setTriggerMsg('')
    try {
      await axios.post('/api/pipeline/trigger', { issue_key: key, description: issueDesc.trim() })
      setTriggerMsg(`Pipeline triggered for ${key}. Watch the progress below.`)
      setIssueKey('')
      setIssueDesc('')
    } catch (err) {
      setTriggerMsg(`Error: ${err.response?.data?.detail ?? err.message}`)
    } finally {
      setTriggering(false)
    }
  }

  const activeRun = runs.find(r => r.status === 'running')

  return (
    <div className="space-y-6">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Autonomous AI Pipeline</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Issue detected → Code analyzed → Fix generated → Code reviewed → Tests written → PR opened
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
          <span className={connected ? 'text-green-400' : 'text-red-400'}>
            {connected ? 'Live' : 'Reconnecting…'}
          </span>
        </div>
      </div>

      {/* ── Pipeline flow diagram ───────────────────────────────────────────── */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
        <div className="flex items-center gap-2 flex-wrap text-xs text-slate-400">
          {[
            { icon: '🔍', label: 'Detect', color: 'bg-indigo-600' },
            { icon: '📖', label: 'Analyze', color: 'bg-rose-600' },
            { icon: '🔧', label: 'Fix', color: 'bg-rose-600' },
            { icon: '👁',  label: 'Review', color: 'bg-amber-500' },
            { icon: '🧪', label: 'Test', color: 'bg-cyan-600' },
            { icon: '📬', label: 'PR', color: 'bg-green-600' },
            { icon: '🎯', label: 'Jira', color: 'bg-blue-600' },
          ].map((step, i, arr) => (
            <span key={step.label} className="flex items-center gap-1.5">
              <span className={`w-5 h-5 rounded-full ${step.color} flex items-center justify-center text-[10px]`}>
                {step.icon}
              </span>
              <span className="font-medium">{step.label}</span>
              {i < arr.length - 1 && <span className="text-slate-600 mx-1">→</span>}
            </span>
          ))}
        </div>
      </div>

      {/* ── Manual trigger ────────────────────────────────────────────────────── */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-white mb-3">
          Trigger Pipeline
          <span className="ml-2 text-xs font-normal text-slate-400">
            (or label a Jira ticket "ai-fix" — it triggers automatically)
          </span>
        </h3>
        <form onSubmit={handleTrigger} className="flex gap-2 flex-wrap">
          <input
            type="text"
            value={issueKey}
            onChange={e => setIssueKey(e.target.value)}
            placeholder="Jira key e.g. MAN-15"
            className="bg-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-rose-500 placeholder:text-slate-500 w-44"
          />
          <input
            type="text"
            value={issueDesc}
            onChange={e => setIssueDesc(e.target.value)}
            placeholder="Brief description (optional)"
            className="flex-1 min-w-48 bg-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-rose-500 placeholder:text-slate-500"
          />
          <button
            type="submit"
            disabled={!issueKey.trim() || triggering}
            className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium disabled:opacity-40 transition-colors flex-shrink-0"
          >
            {triggering ? 'Triggering…' : '▶ Run Pipeline'}
          </button>
        </form>
        {triggerMsg && (
          <p className={`mt-2 text-xs ${triggerMsg.startsWith('Error') ? 'text-red-400' : 'text-green-400'}`}>
            {triggerMsg}
          </p>
        )}
      </div>

      {/* ── Active run ────────────────────────────────────────────────────────── */}
      {activeRun && (
        <div>
          <h3 className="text-xs font-semibold text-rose-400 uppercase tracking-wider mb-2">
            ⚙️ Running Now
          </h3>
          <RunCard run={activeRun} isActive />
        </div>
      )}

      {/* ── History ──────────────────────────────────────────────────────────── */}
      {runs.filter(r => r.status !== 'running').length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Recent Pipeline Runs
          </h3>
          <div className="space-y-2">
            {runs
              .filter(r => r.status !== 'running')
              .map(run => <RunCard key={run.run_id} run={run} isActive={false} />)}
          </div>
        </div>
      )}

      {/* ── Empty state ───────────────────────────────────────────────────────── */}
      {runs.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-slate-600 gap-3">
          <span className="text-4xl">🤖</span>
          <p className="text-sm text-center max-w-xs">
            No pipeline runs yet. Trigger one above, or label a Jira ticket <code className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">ai-fix</code> and the system will pick it up automatically.
          </p>
        </div>
      )}
    </div>
  )
}
