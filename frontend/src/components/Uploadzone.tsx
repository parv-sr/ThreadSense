// frontend/src/components/UploadZone.tsx
import { useCallback, useRef, useState } from "react"
import { uploadFile, pollUntilDone, type TaskStatusResponse } from "../services/api"

type UploadState =
  | { phase: "idle" }
  | { phase: "uploading" }
  | { phase: "polling"; taskId: string; rawfileId: string }
  | { phase: "done"; result: TaskStatusResponse }
  | { phase: "error"; message: string }

interface UploadZoneProps {
  /** Called when the full ingestion + extraction pipeline completes. */
  onComplete?: (result: TaskStatusResponse) => void
}

export default function UploadZone({ onComplete }: UploadZoneProps) {
  const [state, setState] = useState<UploadState>({ phase: "idle" })
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const processFile = useCallback(async (file: File) => {
    // Validate extension client-side
    const ext = file.name.split(".").pop()?.toLowerCase() ?? ""
    if (!["txt", "zip", "rar"].includes(ext)) {
      setState({ phase: "error", message: "Only .txt, .zip, and .rar files are accepted." })
      return
    }

    setState({ phase: "uploading" })
    try {
      const ingestRes = await uploadFile(file)

      if (ingestRes.status === "ALREADY_EXISTS") {
        setState({
          phase: "done",
          result: {
            status: "COMPLETED",
            task_id: ingestRes.task_id,
            result: { note: "File was already processed previously.", rawfile_id: ingestRes.rawfile_id },
          },
        })
        onComplete?.({
          status: "COMPLETED",
          task_id: ingestRes.task_id,
          result: { rawfile_id: ingestRes.rawfile_id },
        })
        return
      }

      setState({ phase: "polling", taskId: ingestRes.task_id, rawfileId: ingestRes.rawfile_id })

      const finalResult = await pollUntilDone(ingestRes.task_id)
      setState({ phase: "done", result: finalResult })
      onComplete?.(finalResult)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed"
      setState({ phase: "error", message })
    }
  }, [onComplete])

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files[0]
      if (file) processFile(file)
    },
    [processFile],
  )

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) processFile(file)
      // reset so the same file can be re-selected
      e.target.value = ""
    },
    [processFile],
  )

  const reset = () => setState({ phase: "idle" })

  // ── Derived UI values ──
  const isActive = state.phase === "uploading" || state.phase === "polling"

  const statusLabel: string = (() => {
    switch (state.phase) {
      case "idle":     return "Drop a WhatsApp export here, or click to browse"
      case "uploading": return "Uploading…"
      case "polling":  return "Ingesting & extracting listings — this may take a minute…"
      case "done":     return "Pipeline complete ✓"
      case "error":    return state.message
    }
  })()

  const dotColor = (() => {
    switch (state.phase) {
      case "done":    return "#22c55e"
      case "error":   return "#ef4444"
      case "polling": return "#f59e0b"
      default:        return "#6366f1"
    }
  })()

  // ── Stats summary ──
  const resultStats =
    state.phase === "done" && typeof state.result.result === "object" && state.result.result
      ? (state.result.result as Record<string, unknown>)
      : null

  return (
    <div style={styles.wrapper}>
      <div
        role="button"
        tabIndex={0}
        aria-label="File upload zone"
        style={{
          ...styles.zone,
          ...(dragging ? styles.zoneDragging : {}),
          ...(isActive ? styles.zoneActive : {}),
          ...(state.phase === "error" ? styles.zoneError : {}),
          ...(state.phase === "done" ? styles.zoneDone : {}),
          cursor: isActive ? "wait" : "pointer",
        }}
        onClick={() => !isActive && inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && !isActive && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".txt,.zip,.rar"
          style={{ display: "none" }}
          onChange={handleFileChange}
        />

        {/* Animated dot */}
        <span
          style={{
            ...styles.dot,
            backgroundColor: dotColor,
            animation: isActive ? "pulse 1.2s ease-in-out infinite" : "none",
          }}
        />

        {/* Primary label */}
        <p style={styles.label}>{statusLabel}</p>

        {/* Polling task info */}
        {state.phase === "polling" && (
          <p style={styles.sub}>Task ID: <code style={styles.code}>{state.taskId}</code></p>
        )}

        {/* Done stats */}
        {state.phase === "done" && resultStats && (
          <div style={styles.statsGrid}>
            {["created", "ignored", "processed", "failed"].map((key) =>
              resultStats[key] !== undefined ? (
                <div key={key} style={styles.statItem}>
                  <span style={styles.statValue}>{String(resultStats[key])}</span>
                  <span style={styles.statKey}>{key}</span>
                </div>
              ) : null,
            )}
          </div>
        )}

        {/* Reset / try again */}
        {(state.phase === "done" || state.phase === "error") && (
          <button
            style={styles.resetBtn}
            onClick={(e) => { e.stopPropagation(); reset() }}
          >
            {state.phase === "error" ? "Try again" : "Upload another"}
          </button>
        )}
      </div>

      {/* Inline keyframe style */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.4; transform: scale(1.35); }
        }
      `}</style>
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    width: "100%",
    maxWidth: 560,
    margin: "0 auto",
    fontFamily: "'DM Mono', 'Fira Mono', monospace",
  },
  zone: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    padding: "40px 32px",
    borderRadius: 16,
    border: "2px dashed #334155",
    background: "#0f172a",
    color: "#94a3b8",
    transition: "border-color 0.2s, background 0.2s",
    minHeight: 200,
    outline: "none",
    userSelect: "none",
  },
  zoneDragging: {
    borderColor: "#6366f1",
    background: "#1e1b4b",
  },
  zoneActive: {
    borderColor: "#f59e0b",
    background: "#1c1612",
  },
  zoneDone: {
    borderColor: "#22c55e",
    background: "#052e16",
  },
  zoneError: {
    borderColor: "#ef4444",
    background: "#1c0707",
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: "50%",
    display: "inline-block",
  },
  label: {
    margin: 0,
    fontSize: 14,
    textAlign: "center",
    lineHeight: 1.5,
    color: "#cbd5e1",
  },
  sub: {
    margin: 0,
    fontSize: 12,
    color: "#64748b",
  },
  code: {
    background: "#1e293b",
    padding: "2px 6px",
    borderRadius: 4,
    fontSize: 11,
    color: "#a5b4fc",
  },
  statsGrid: {
    display: "flex",
    gap: 24,
    marginTop: 8,
  },
  statItem: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 2,
  },
  statValue: {
    fontSize: 22,
    fontWeight: 700,
    color: "#f1f5f9",
  },
  statKey: {
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#475569",
  },
  resetBtn: {
    marginTop: 8,
    padding: "6px 18px",
    borderRadius: 8,
    border: "1px solid #334155",
    background: "transparent",
    color: "#94a3b8",
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "border-color 0.15s, color 0.15s",
  },
}