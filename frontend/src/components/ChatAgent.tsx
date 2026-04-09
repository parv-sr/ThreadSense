// frontend/src/components/ChatAgent.tsx
import { useCallback, useEffect, useRef, useState } from "react"
import { sendChatMessage, fetchSource, type ChatResponse, type SourceResponse } from "../services/api"

// ─── Types ────────────────────────────────────────────────────────────────────

type Role = "user" | "assistant"

interface Message {
  id: string
  role: Role
  text: string
  response?: ChatResponse
  error?: string
  loading?: boolean
}

interface SourceDrawerProps {
  source: SourceResponse
  onClose: () => void
}

// ─── Source Drawer ─────────────────────────────────────────────────────────────

function SourceDrawer({ source, onClose }: SourceDrawerProps) {
  return (
    <div style={ds.overlay} onClick={onClose}>
      <div style={ds.drawer} onClick={(e) => e.stopPropagation()}>
        <header style={ds.drawerHeader}>
          <span style={ds.drawerTitle}>Source chunk</span>
          <button style={ds.closeBtn} onClick={onClose} aria-label="Close">✕</button>
        </header>
        <dl style={ds.dl}>
          {[
            ["Sender", source.sender],
            ["Timestamp", source.message_start],
            ["Status", source.status],
          ].map(([label, val]) =>
            val ? (
              <div key={label as string} style={ds.dlRow}>
                <dt style={ds.dt}>{label}</dt>
                <dd style={ds.dd}>{val}</dd>
              </div>
            ) : null,
          )}
        </dl>
        <p style={ds.rawLabel}>Raw text</p>
        <pre style={ds.pre}>{source.raw_text}</pre>
        {source.cleaned_text && source.cleaned_text !== source.raw_text && (
          <>
            <p style={ds.rawLabel}>Cleaned text</p>
            <pre style={ds.pre}>{source.cleaned_text}</pre>
          </>
        )}
      </div>
    </div>
  )
}

// ─── Main component ────────────────────────────────────────────────────────────

export default function ChatAgent() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [threadId, setThreadId] = useState<string | null>(null)
  const [source, setSource] = useState<SourceResponse | null>(null)
  const [loadingSource, setLoadingSource] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Listen for View Source custom events fired by rendered table HTML
  useEffect(() => {
    const handler = async (e: Event) => {
      const detail = (e as CustomEvent<{ chunk_id: string }>).detail
      if (!detail?.chunk_id) return
      setLoadingSource(detail.chunk_id)
      try {
        const s = await fetchSource(detail.chunk_id)
        setSource(s)
      } catch {
        // silently ignore
      } finally {
        setLoadingSource(null)
      }
    }
    window.addEventListener("threadsense:source", handler)
    return () => window.removeEventListener("threadsense:source", handler)
  }, [])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text) return

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      text,
    }
    const placeholderMsg: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      text: "",
      loading: true,
    }

    setMessages((prev) => [...prev, userMsg, placeholderMsg])
    setInput("")

    try {
      const response = await sendChatMessage({ message: text, thread_id: threadId })

      // Persist thread_id for conversational continuity
      if (!threadId) setThreadId(response.thread_id)

      setMessages((prev) =>
        prev.map((m) =>
          m.id === placeholderMsg.id
            ? { ...m, loading: false, text: response.reasoning, response }
            : m,
        ),
      )
    } catch (err) {
      const errorText = err instanceof Error ? err.message : "Request failed"
      setMessages((prev) =>
        prev.map((m) =>
          m.id === placeholderMsg.id
            ? { ...m, loading: false, error: errorText }
            : m,
        ),
      )
    }
  }, [input, threadId])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const isStreaming = messages.some((m) => m.loading)

  return (
    <div style={cs.wrapper}>
      {/* ── Thread badge ── */}
      {threadId && (
        <div style={cs.threadBadge}>
          <span style={cs.threadDot} />
          Thread: <code style={cs.code}>{threadId.slice(0, 8)}…</code>
        </div>
      )}

      {/* ── Message list ── */}
      <div style={cs.messageList}>
        {messages.length === 0 && (
          <div style={cs.emptyState}>
            <p style={cs.emptyTitle}>ThreadSense</p>
            <p style={cs.emptySub}>Ask anything about your WhatsApp property listings.</p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              ...cs.messageRow,
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                ...cs.bubble,
                ...(msg.role === "user" ? cs.userBubble : cs.assistantBubble),
                ...(msg.error ? cs.errorBubble : {}),
              }}
            >
              {/* Loading pulse */}
              {msg.loading && (
                <span style={cs.typingDots}>
                  <span style={{ ...cs.dot, animationDelay: "0ms" }} />
                  <span style={{ ...cs.dot, animationDelay: "160ms" }} />
                  <span style={{ ...cs.dot, animationDelay: "320ms" }} />
                </span>
              )}

              {/* Error */}
              {msg.error && <p style={cs.errorText}>⚠ {msg.error}</p>}

              {/* Assistant reasoning */}
              {!msg.loading && !msg.error && msg.role === "assistant" && msg.text && (
                <p style={cs.reasoning}>{msg.text}</p>
              )}

              {/* User text */}
              {msg.role === "user" && <p style={cs.userText}>{msg.text}</p>}

              {/* Results table */}
              {msg.response?.table_html && (
                <div
                  style={cs.tableWrapper}
                  // Safe — the HTML is server-rendered by our own backend
                  dangerouslySetInnerHTML={{ __html: msg.response.table_html }}
                />
              )}

              {/* Sources */}
              {msg.response && msg.response.sources.length > 0 && (
                <div style={cs.sourcesList}>
                  <span style={cs.sourcesLabel}>Sources</span>
                  {msg.response.sources.slice(0, 8).map((id) => (
                    <button
                      key={id}
                      style={{
                        ...cs.sourceChip,
                        ...(loadingSource === id ? cs.sourceChipLoading : {}),
                      }}
                      onClick={async () => {
                        setLoadingSource(id)
                        try {
                          const s = await fetchSource(id)
                          setSource(s)
                        } catch {
                          // ignore
                        } finally {
                          setLoadingSource(null)
                        }
                      }}
                    >
                      {loadingSource === id ? "…" : id.slice(0, 8)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* ── Input bar ── */}
      <div style={cs.inputBar}>
        <textarea
          ref={textareaRef}
          style={cs.textarea}
          placeholder="Ask about properties — 2 BHK in Bandra under 80k…"
          value={input}
          rows={1}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
        />
        <button
          style={{
            ...cs.sendBtn,
            ...(isStreaming || !input.trim() ? cs.sendBtnDisabled : {}),
          }}
          onClick={sendMessage}
          disabled={isStreaming || !input.trim()}
          aria-label="Send"
        >
          ↑
        </button>
      </div>

      {/* ── Source drawer ── */}
      {source && <SourceDrawer source={source} onClose={() => setSource(null)} />}

      {/* Inline keyframe */}
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40%            { transform: translateY(-5px); opacity: 1; }
        }
        .threadsense-table table {
          width: 100%;
          border-collapse: collapse;
          font-size: 12px;
          margin-top: 12px;
        }
        .threadsense-table th {
          background: #1e293b;
          color: #94a3b8;
          padding: 6px 10px;
          text-align: left;
          font-weight: 500;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          font-size: 10px;
        }
        .threadsense-table td {
          padding: 6px 10px;
          border-bottom: 1px solid #1e293b;
          color: #e2e8f0;
        }
        .threadsense-table tr:hover td { background: #1e293b44; }
        .view-source-btn {
          background: #6366f1;
          color: #fff;
          border: none;
          padding: 3px 8px;
          border-radius: 4px;
          font-size: 11px;
          cursor: pointer;
        }
      `}</style>
    </div>
  )
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const cs: Record<string, React.CSSProperties> = {
  wrapper: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    maxHeight: "100vh",
    background: "#080e1a",
    fontFamily: "'DM Mono', 'Fira Mono', monospace",
    color: "#e2e8f0",
    position: "relative",
  },
  threadBadge: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "8px 16px",
    fontSize: 11,
    color: "#475569",
    borderBottom: "1px solid #1e293b",
  },
  threadDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#22c55e",
    display: "inline-block",
  },
  code: {
    background: "#1e293b",
    padding: "1px 5px",
    borderRadius: 3,
    color: "#a5b4fc",
    fontSize: 10,
  },
  messageList: {
    flex: 1,
    overflowY: "auto",
    padding: "24px 16px",
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  emptyState: {
    margin: "auto",
    textAlign: "center",
    color: "#334155",
    padding: "60px 0",
  },
  emptyTitle: {
    fontSize: 28,
    fontWeight: 700,
    margin: "0 0 8px",
    color: "#1e293b",
    letterSpacing: "-0.02em",
  },
  emptySub: {
    fontSize: 13,
    margin: 0,
  },
  messageRow: {
    display: "flex",
    width: "100%",
  },
  bubble: {
    maxWidth: "82%",
    borderRadius: 14,
    padding: "12px 16px",
    lineHeight: 1.6,
  },
  userBubble: {
    background: "#1e1b4b",
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    background: "#0f172a",
    border: "1px solid #1e293b",
    borderBottomLeftRadius: 4,
    maxWidth: "100%",
    width: "100%",
  },
  errorBubble: {
    background: "#1c0707",
    border: "1px solid #7f1d1d",
  },
  typingDots: {
    display: "flex",
    gap: 4,
    padding: "4px 0",
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: "#6366f1",
    display: "inline-block",
    animation: "bounce 1.2s ease-in-out infinite",
  },
  reasoning: {
    margin: 0,
    fontSize: 14,
    color: "#cbd5e1",
    whiteSpace: "pre-wrap",
  },
  userText: {
    margin: 0,
    fontSize: 14,
    color: "#e2e8f0",
  },
  errorText: {
    margin: 0,
    fontSize: 13,
    color: "#fca5a5",
  },
  tableWrapper: {
    marginTop: 12,
    overflowX: "auto",
    // className injected via dangerouslySetInnerHTML won't work, use a wrapper class
    // styles are applied via the <style> block above
    fontFamily: "inherit",
  },
  sourcesList: {
    display: "flex",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 12,
    alignItems: "center",
  },
  sourcesLabel: {
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#475569",
    marginRight: 4,
  },
  sourceChip: {
    padding: "3px 10px",
    borderRadius: 20,
    background: "#1e293b",
    border: "1px solid #334155",
    color: "#a5b4fc",
    fontSize: 11,
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "background 0.15s",
  },
  sourceChipLoading: {
    background: "#312e81",
    color: "#c7d2fe",
  },
  inputBar: {
    display: "flex",
    gap: 8,
    padding: "12px 16px",
    borderTop: "1px solid #1e293b",
    background: "#0b1220",
    alignItems: "flex-end",
  },
  textarea: {
    flex: 1,
    background: "#0f172a",
    border: "1px solid #1e293b",
    borderRadius: 10,
    color: "#e2e8f0",
    fontSize: 14,
    padding: "10px 14px",
    resize: "none",
    outline: "none",
    fontFamily: "inherit",
    lineHeight: 1.5,
    transition: "border-color 0.15s",
    overflowY: "auto",
    maxHeight: 120,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 10,
    background: "#6366f1",
    border: "none",
    color: "#fff",
    fontSize: 18,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    transition: "background 0.15s, transform 0.1s",
  },
  sendBtnDisabled: {
    background: "#1e293b",
    color: "#475569",
    cursor: "not-allowed",
  },
}

// ─── Drawer styles ────────────────────────────────────────────────────────────

const ds: Record<string, React.CSSProperties> = {
  overlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.6)",
    zIndex: 1000,
    display: "flex",
    justifyContent: "flex-end",
  },
  drawer: {
    width: "min(480px, 95vw)",
    background: "#0f172a",
    borderLeft: "1px solid #1e293b",
    overflowY: "auto",
    padding: 24,
    display: "flex",
    flexDirection: "column",
    gap: 12,
    fontFamily: "'DM Mono', monospace",
  },
  drawerHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  drawerTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: "#e2e8f0",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
  closeBtn: {
    background: "transparent",
    border: "none",
    color: "#475569",
    fontSize: 16,
    cursor: "pointer",
    padding: "2px 6px",
  },
  dl: { margin: 0, padding: 0 },
  dlRow: {
    display: "flex",
    gap: 12,
    padding: "4px 0",
    borderBottom: "1px solid #1e293b",
    fontSize: 12,
  },
  dt: { color: "#475569", minWidth: 90 },
  dd: { margin: 0, color: "#94a3b8" },
  rawLabel: {
    margin: "8px 0 4px",
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#334155",
  },
  pre: {
    margin: 0,
    background: "#020617",
    border: "1px solid #1e293b",
    borderRadius: 8,
    padding: 12,
    fontSize: 12,
    color: "#94a3b8",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    lineHeight: 1.6,
    overflowY: "auto",
    maxHeight: 320,
  },
}