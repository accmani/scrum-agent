import { useState, useRef, useEffect } from 'react'
import { sendChat, fixIssue } from '../api'

const AGENTS = [
  { value: null,           label: 'All Agents (default)',  avatar: 'S',  color: 'bg-indigo-600' },
  { value: 'scrum_master', label: 'Scrum Master',          avatar: 'SM', color: 'bg-indigo-500' },
  { value: 'jira',         label: 'Jira Agent',            avatar: 'J',  color: 'bg-blue-600'   },
  { value: 'github',       label: 'GitHub Agent',          avatar: 'GH', color: 'bg-purple-600' },
  { value: 'standup',      label: 'Standup Agent',         avatar: 'ST', color: 'bg-green-600'  },
  { value: 'planning',     label: 'Planning Agent',        avatar: 'P',  color: 'bg-orange-500' },
  { value: 'code_fix',     label: 'Code Fix Agent',        avatar: 'CF', color: 'bg-rose-600'   },
]

// Extract Jira key (e.g. PROJ-42) or GitHub issue number (gh-15 / #15) from free text
function parseIssueKey(text) {
  const jira = text.match(/\b([A-Z]+-\d+)\b/)
  if (jira) return jira[1]
  const gh = text.match(/\b(?:gh-|#)(\d+)\b/i)
  if (gh) return `gh-${gh[1]}`
  return text.trim()
}

function Bubble({ msg, agentColor }) {
  const isUser = msg.role === 'user'
  const bg = agentColor ?? 'bg-indigo-600'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} gap-2`}>
      {!isUser && (
        <div className={`w-7 h-7 rounded-full ${bg} flex items-center justify-center text-xs font-bold text-white shrink-0 mt-1`}>
          A
        </div>
      )}
      <div
        className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-indigo-600 text-white rounded-br-sm'
            : 'bg-slate-700 text-slate-100 rounded-bl-sm'
        }`}
      >
        {msg.content}
      </div>
      {isUser && (
        <div className="w-7 h-7 rounded-full bg-slate-600 flex items-center justify-center text-xs font-bold text-slate-300 shrink-0 mt-1">
          U
        </div>
      )}
    </div>
  )
}

function TypingIndicator({ agentColor, label }) {
  const bg = agentColor ?? 'bg-indigo-600'
  return (
    <div className="flex items-center gap-2">
      <div className={`w-7 h-7 rounded-full ${bg} flex items-center justify-center text-xs font-bold text-white shrink-0`}>
        A
      </div>
      <div className="bg-slate-700 rounded-2xl rounded-bl-sm px-4 py-3 flex gap-2 items-center">
        {[0, 1, 2].map(i => (
          <span key={i} className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: `${i * 150}ms` }} />
        ))}
        {label && <span className="text-xs text-slate-400 ml-1">{label}</span>}
      </div>
    </div>
  )
}

function ActionBanner({ result }) {
  if (!result) return null

  // PR / code-fix result
  if (result.pr_url) {
    return (
      <div className="bg-rose-900/30 border border-rose-700/50 rounded-xl px-4 py-3 text-sm text-rose-200 space-y-1">
        <div className="font-semibold text-rose-300">Pull Request created</div>
        {result.jira_key && (
          <div className="text-xs text-rose-400">Jira ticket <span className="font-mono">{result.jira_key}</span> → In Review</div>
        )}
        {result.branch && (
          <div className="text-xs text-rose-400">Branch: <span className="font-mono">{result.branch}</span></div>
        )}
        {result.files_changed?.length > 0 && (
          <div className="text-xs text-rose-400">
            Files changed: {result.files_changed.map(f => (
              <span key={f} className="font-mono bg-rose-900/40 px-1 rounded mr-1">{f}</span>
            ))}
          </div>
        )}
        <a
          href={result.pr_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 mt-1 text-xs font-medium text-rose-300 underline hover:text-rose-200"
        >
          View PR #{result.pr_number} →
        </a>
      </div>
    )
  }

  // Standard Jira action result
  return (
    <div className="bg-green-900/30 border border-green-700/50 rounded-xl px-4 py-3 text-sm text-green-300">
      <span className="font-medium">Action completed: </span>
      {result.key && `${result.key} `}
      {result.new_status && `→ ${result.new_status}`}
      {result.url && (
        <a
          href={result.url}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-2 underline text-green-400 hover:text-green-300"
        >
          View
        </a>
      )}
    </div>
  )
}

export default function Chat({ refresh }) {
  const [history, setHistory] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingLabel, setLoadingLabel] = useState('')
  const [actionResult, setActionResult] = useState(null)
  const [selectedAgent, setSelectedAgent] = useState(AGENTS[0])
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, loading])

  async function handleSend(e) {
    e?.preventDefault()
    const text = input.trim()
    if (!text || loading) return

    const userMsg = { role: 'user', content: text }
    setHistory(h => [...h, userMsg])
    setInput('')
    setLoading(true)
    setActionResult(null)

    try {
      if (selectedAgent.value === 'code_fix') {
        // Code Fix Agent: call the dedicated fix-issue endpoint
        setLoadingLabel('Analyzing code & generating fix…')
        const issueKey = parseIssueKey(text)
        // Strip the key from the description to pass as extra context
        const description = text.replace(/\b[A-Z]+-\d+\b/g, '').replace(/\b(?:gh-|#)\d+\b/gi, '').trim()
        const data = await fixIssue(issueKey, description)
        const summary = data.pr_url
          ? `PR created: ${data.pr_url}\nBranch: ${data.branch}\nFiles changed: ${data.files_changed?.join(', ')}`
          : `Fix failed: ${data.error ?? 'unknown error'}`
        setHistory(h => [...h, { role: 'assistant', content: summary }])
        setActionResult(data)
        await refresh()
      } else {
        setLoadingLabel('')
        const data = await sendChat(text, [...history, userMsg], selectedAgent.value)
        setHistory(h => [...h, { role: 'assistant', content: data.reply }])
        if (data.action_result) {
          setActionResult(data.action_result)
          await refresh()
        }
      }
    } catch (err) {
      setHistory(h => [
        ...h,
        { role: 'assistant', content: `Error: ${err.response?.data?.detail ?? err.message}` },
      ])
    } finally {
      setLoading(false)
      setLoadingLabel('')
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isCodeFix = selectedAgent.value === 'code_fix'

  const defaultPrompts = isCodeFix
    ? ['Fix PROJ-42', 'Fix gh-15', 'Fix the login timeout bug in PROJ-7', 'Fix #23 null pointer crash']
    : ["What's blocking the team?", 'Move PROJ-12 to Done', 'Create a ticket for login bug', 'Summarize sprint progress']

  return (
    <div className="flex flex-col h-[calc(100vh-140px)]">
      {/* Agent selector */}
      <div className="flex items-center gap-3 mb-4 pb-4 border-b border-slate-700">
        <span className="text-xs text-slate-500 shrink-0">Talk to:</span>
        <div className="flex flex-wrap gap-2">
          {AGENTS.map(ag => (
            <button
              key={ag.label}
              onClick={() => { setSelectedAgent(ag); setActionResult(null) }}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                selectedAgent.value === ag.value
                  ? `${ag.color} text-white`
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              <span className={`w-4 h-4 rounded-full ${ag.color} flex items-center justify-center text-[8px] text-white font-bold`}>
                {ag.avatar[0]}
              </span>
              {ag.label}
            </button>
          ))}
        </div>
      </div>

      {/* Code Fix Agent hint */}
      {isCodeFix && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-rose-900/20 border border-rose-700/30 text-xs text-rose-300">
          <span className="font-semibold">Code Fix Agent</span> — type a Jira key or GitHub issue number (e.g.{' '}
          <code className="bg-rose-900/40 px-1 rounded">Fix PROJ-42</code> or{' '}
          <code className="bg-rose-900/40 px-1 rounded">Fix gh-15</code>). The agent will read your code,
          generate a fix, and open a Pull Request. This may take ~30 seconds.
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-4 flex flex-col gap-4">
        {history.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-3">
            <div className={`w-14 h-14 rounded-full ${selectedAgent.color}/20 border border-current/30 flex items-center justify-center text-2xl`}>
              {isCodeFix ? '🔧' : '🤖'}
            </div>
            <p className="text-sm text-center max-w-sm">
              {isCodeFix
                ? 'Give me a Jira ticket or GitHub issue number and I\'ll read the code, generate a fix, and open a PR.'
                : 'Ask me anything about your sprint — I can move tickets, create stories, and summarize progress.'}
            </p>
            <div className="flex flex-wrap gap-2 justify-center mt-1">
              {defaultPrompts.map(s => (
                <button
                  key={s}
                  onClick={() => { setInput(s); textareaRef.current?.focus() }}
                  className="text-xs px-3 py-1.5 rounded-full bg-slate-700 hover:bg-slate-600 text-slate-300 border border-slate-600 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {history.map((msg, i) => <Bubble key={i} msg={msg} agentColor={selectedAgent.color} />)}
        {loading && <TypingIndicator agentColor={selectedAgent.color} label={loadingLabel} />}

        {/* Action result banner */}
        {actionResult && !loading && <ActionBanner result={actionResult} />}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-slate-700 pt-4">
        <form onSubmit={handleSend} className="flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder={
              isCodeFix
                ? 'Type a Jira key or GitHub issue (e.g. "Fix PROJ-42")… Enter to send'
                : `Ask ${selectedAgent.label}… (Enter to send, Shift+Enter for newline)`
            }
            className="flex-1 bg-slate-700 rounded-xl px-4 py-3 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-500 resize-none max-h-36 overflow-y-auto"
            style={{ height: 'auto' }}
            onInput={e => {
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 144) + 'px'
            }}
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className={`px-4 py-3 rounded-xl text-white disabled:opacity-40 transition-colors shrink-0 ${
              isCodeFix ? 'bg-rose-600 hover:bg-rose-500' : 'bg-indigo-600 hover:bg-indigo-500'
            }`}
          >
            {isCodeFix ? (
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2v-4M9 21H5a2 2 0 0 1-2-2v-4m0 0h18" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            ) : (
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M22 2L11 13M22 2L15 22 11 13 2 9l20-7z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
