import { useState, useEffect, useRef, useCallback } from 'react'

// Maps agent color tokens → Tailwind classes (must be static strings for PurgeCSS)
const COLOR_MAP = {
  indigo:  { bg: 'bg-indigo-600',  ring: 'ring-indigo-500/40',  text: 'text-indigo-400'  },
  blue:    { bg: 'bg-blue-600',    ring: 'ring-blue-500/40',    text: 'text-blue-400'    },
  purple:  { bg: 'bg-purple-600',  ring: 'ring-purple-500/40',  text: 'text-purple-400'  },
  green:   { bg: 'bg-green-600',   ring: 'ring-green-500/40',   text: 'text-green-400'   },
  orange:  { bg: 'bg-orange-500',  ring: 'ring-orange-500/40',  text: 'text-orange-400'  },
  slate:   { bg: 'bg-slate-600',   ring: 'ring-slate-500/40',   text: 'text-slate-400'   },
}

function colorOf(color) {
  return COLOR_MAP[color] ?? COLOR_MAP.slate
}

function AgentAvatar({ displayName, color }) {
  const { bg } = colorOf(color)
  const initials = displayName
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
  return (
    <div className={`w-8 h-8 rounded-full ${bg} flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0`}>
      {initials}
    </div>
  )
}

function ThinkingDots() {
  return (
    <span className="inline-flex items-center gap-1">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-current animate-bounce"
          style={{ animationDelay: `${i * 150}ms` }}
        />
      ))}
    </span>
  )
}

function AgentBubble({ msg }) {
  const { text, ring } = colorOf(msg.color)

  if (msg.type === 'thinking') {
    return (
      <div className="flex items-start gap-3">
        <AgentAvatar displayName={msg.display_name} color={msg.color} />
        <div className={`bg-slate-800 rounded-2xl rounded-tl-sm px-4 py-3 ring-1 ${ring} max-w-[75%]`}>
          <p className={`text-xs font-semibold mb-1 ${text}`}>{msg.display_name}</p>
          <p className={`text-sm ${text}`}><ThinkingDots /></p>
        </div>
      </div>
    )
  }

  if (msg.type === 'error') {
    return (
      <div className="flex items-start gap-3">
        <AgentAvatar displayName={msg.display_name} color={msg.color} />
        <div className="bg-red-900/30 rounded-2xl rounded-tl-sm px-4 py-3 ring-1 ring-red-500/30 max-w-[75%]">
          <p className="text-xs font-semibold mb-1 text-red-400">{msg.display_name}</p>
          <p className="text-sm text-red-300">{msg.text}</p>
        </div>
      </div>
    )
  }

  // type === 'message'
  return (
    <div className="flex items-start gap-3">
      <AgentAvatar displayName={msg.display_name} color={msg.color} />
      <div className={`bg-slate-800 rounded-2xl rounded-tl-sm px-4 py-3 ring-1 ${ring} max-w-[75%]`}>
        <p className={`text-xs font-semibold mb-1 ${text}`}>{msg.display_name}</p>
        <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{msg.text}</p>
      </div>
    </div>
  )
}

function UserBubble({ text }) {
  return (
    <div className="flex justify-end">
      <div className="bg-indigo-600 rounded-2xl rounded-tr-sm px-4 py-3 max-w-[75%]">
        <p className="text-sm text-white leading-relaxed">{text}</p>
      </div>
    </div>
  )
}

// Use the same host/port as the page so Vite's proxy forwards the WebSocket.
const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`

const QUICK_PROMPTS = [
  'Generate today\'s standup',
  'Any blockers I should know about?',
  'What should we pull into the next sprint?',
  'Summarise GitHub issues vs Jira tickets',
]

export default function TeamChat() {
  const [messages, setMessages]   = useState([])
  const [input, setInput]         = useState('')
  const [connected, setConnected] = useState(false)
  const [waiting, setWaiting]     = useState(false)

  const wsRef       = useRef(null)
  const bottomRef   = useRef(null)
  // Track which agents are still "thinking" in the current round
  const thinkingRef = useRef(new Set())

  const scrollToBottom = () =>
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })

  // ── WebSocket lifecycle ──────────────────────────────────────────────────
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)

    ws.onclose = () => {
      setConnected(false)
      // Auto-reconnect after 3 s
      setTimeout(connect, 3000)
    }

    ws.onerror = () => ws.close()

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)

      if (msg.type === 'done') {
        // Remove all thinking bubbles that haven't been replaced
        setMessages(prev =>
          prev.filter(m => m.type !== 'thinking')
        )
        thinkingRef.current.clear()
        setWaiting(false)
        return
      }

      if (msg.type === 'thinking') {
        thinkingRef.current.add(msg.agent)
        setMessages(prev => [...prev, { ...msg, id: `think-${msg.agent}` }])
      } else {
        // Replace the thinking bubble for this agent with the real message
        setMessages(prev => {
          const without = prev.filter(m => m.id !== `think-${msg.agent}`)
          return [...without, { ...msg, id: `msg-${msg.agent}-${Date.now()}` }]
        })
        thinkingRef.current.delete(msg.agent)
      }
    }
  }, [])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  useEffect(scrollToBottom, [messages])

  // ── Send ─────────────────────────────────────────────────────────────────
  function send(text) {
    const trimmed = text.trim()
    if (!trimmed || !connected || waiting) return

    // Append user bubble
    setMessages(prev => [...prev, { type: 'user', text: trimmed, id: `user-${Date.now()}` }])
    setInput('')
    setWaiting(true)
    thinkingRef.current.clear()

    wsRef.current.send(JSON.stringify({ message: trimmed }))
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-[80vh]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Team Chat</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            5 specialized agents respond in parallel
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
          <span className={connected ? 'text-green-400' : 'text-red-400'}>
            {connected ? 'Connected' : 'Reconnecting…'}
          </span>
        </div>
      </div>

      {/* Agent legend */}
      <div className="flex flex-wrap gap-2 mb-4">
        {[
          { name: 'Scrum Master', color: 'indigo' },
          { name: 'Jira Agent',   color: 'blue'   },
          { name: 'GitHub Agent', color: 'purple' },
          { name: 'Standup Agent',color: 'green'  },
          { name: 'Planning Agent',color:'orange' },
        ].map(a => {
          const { bg } = colorOf(a.color)
          return (
            <div key={a.name} className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${bg}`} />
              <span className="text-[10px] text-slate-400">{a.name}</span>
            </div>
          )
        })}
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-4 pr-1 scroll-smooth">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-slate-600">
            <span className="text-4xl">💬</span>
            <p className="text-sm">Ask anything — all 5 agents will weigh in</p>
          </div>
        )}

        {messages.map(msg =>
          msg.type === 'user'
            ? <UserBubble key={msg.id} text={msg.text} />
            : <AgentBubble key={msg.id} msg={msg} />
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick prompts */}
      {!waiting && messages.length === 0 && (
        <div className="flex flex-wrap gap-2 mt-4 mb-3">
          {QUICK_PROMPTS.map(p => (
            <button
              key={p}
              onClick={() => send(p)}
              disabled={!connected}
              className="text-xs px-3 py-1.5 rounded-full bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors disabled:opacity-40"
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div className="mt-4 flex gap-2">
        <textarea
          rows={1}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={!connected || waiting}
          placeholder={waiting ? 'Waiting for agents…' : 'Ask the team… (Enter to send)'}
          className="flex-1 bg-slate-800 rounded-xl px-4 py-3 text-sm text-slate-100 outline-none
            focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-600 resize-none
            disabled:opacity-50 transition-all"
        />
        <button
          onClick={() => send(input)}
          disabled={!connected || waiting || !input.trim()}
          className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium
            disabled:opacity-40 transition-colors flex-shrink-0"
        >
          Send
        </button>
      </div>
    </div>
  )
}
