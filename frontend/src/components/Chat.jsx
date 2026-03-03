import { useState, useRef, useEffect } from 'react'
import { sendChat } from '../api'

const AGENTS = [
  { value: null,           label: 'All Agents (default)',  avatar: 'S', color: 'bg-indigo-600' },
  { value: 'scrum_master', label: 'Scrum Master',          avatar: 'SM', color: 'bg-indigo-500' },
  { value: 'jira',         label: 'Jira Agent',            avatar: 'J',  color: 'bg-blue-600' },
  { value: 'github',       label: 'GitHub Agent',          avatar: 'GH', color: 'bg-purple-600' },
  { value: 'standup',      label: 'Standup Agent',         avatar: 'ST', color: 'bg-green-600' },
  { value: 'planning',     label: 'Planning Agent',        avatar: 'P',  color: 'bg-orange-500' },
]

function Bubble({ msg, agentColor }) {
  const isUser = msg.role === 'user'
  const bg = agentColor ?? 'bg-indigo-600'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} gap-2`}>
      {!isUser && (
        <div className={`w-7 h-7 rounded-full ${bg} flex items-center justify-center text-xs font-bold text-white shrink-0 mt-1`}>
          S
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

function TypingIndicator({ agentColor }) {
  const bg = agentColor ?? 'bg-indigo-600'
  return (
    <div className="flex items-center gap-2">
      <div className={`w-7 h-7 rounded-full ${bg} flex items-center justify-center text-xs font-bold text-white shrink-0`}>
        S
      </div>
      <div className="bg-slate-700 rounded-2xl rounded-bl-sm px-4 py-3 flex gap-1.5 items-center">
        {[0, 1, 2].map(i => (
          <span key={i} className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: `${i * 150}ms` }} />
        ))}
      </div>
    </div>
  )
}

export default function Chat({ refresh }) {
  const [history, setHistory] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
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
      const data = await sendChat(text, [...history, userMsg], selectedAgent.value)
      setHistory(h => [...h, { role: 'assistant', content: data.reply }])
      if (data.action_result) {
        setActionResult(data.action_result)
        await refresh()
      }
    } catch (err) {
      setHistory(h => [
        ...h,
        { role: 'assistant', content: `Error: ${err.response?.data?.detail ?? err.message}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-140px)]">
      {/* Agent selector */}
      <div className="flex items-center gap-3 mb-4 pb-4 border-b border-slate-700">
        <span className="text-xs text-slate-500 shrink-0">Talk to:</span>
        <div className="flex flex-wrap gap-2">
          {AGENTS.map(ag => (
            <button
              key={ag.label}
              onClick={() => setSelectedAgent(ag)}
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

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-4 flex flex-col gap-4">
        {history.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-3">
            <div className="w-14 h-14 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-2xl">
              🤖
            </div>
            <p className="text-sm text-center max-w-sm">
              Ask me anything about your sprint — I can move tickets, create stories, and summarize progress.
            </p>
            <div className="flex flex-wrap gap-2 justify-center mt-1">
              {[
                'What\'s blocking the team?',
                'Move PROJ-12 to Done',
                'Create a ticket for login bug',
                'Summarize sprint progress',
              ].map(s => (
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
        {loading && <TypingIndicator agentColor={selectedAgent.color} />}

        {/* Action result banner */}
        {actionResult && !loading && (
          <div className="bg-green-900/30 border border-green-700/50 rounded-xl px-4 py-3 text-sm text-green-300">
            <span className="font-medium">Action completed: </span>
            {actionResult.key && `${actionResult.key} `}
            {actionResult.new_status && `→ ${actionResult.new_status}`}
            {actionResult.url && (
              <a
                href={actionResult.url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-2 underline text-green-400 hover:text-green-300"
              >
                View
              </a>
            )}
          </div>
        )}
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
            placeholder={`Ask ${selectedAgent.label}… (Enter to send, Shift+Enter for newline)`}
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
            className="px-4 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40 transition-colors shrink-0"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M22 2L11 13M22 2L15 22 11 13 2 9l20-7z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  )
}
