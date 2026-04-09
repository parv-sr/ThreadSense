// frontend/src/api.ts
// Typed API client for all ThreadSense backend calls.

const BASE_URL = import.meta.env.VITE_API_URL ?? ""

// ─── Types ────────────────────────────────────────────────────────────────────

export interface IngestResponse {
  task_id: string
  rawfile_id: string
  status: "QUEUED" | "ALREADY_EXISTS"
}

export interface TaskStatusResponse {
  status: "PENDING" | "COMPLETED" | "FAILED" | "PROCESSING" | string
  task_id: string
  result?: Record<string, unknown>
  error?: string
}

export interface ChatRequest {
  message: string
  thread_id?: string | null
}

export interface ChatResponse {
  thread_id: string
  table_html: string
  reasoning: string
  sources: string[]
}

export interface SourceResponse {
  chunk_id: string
  message_start: string | null
  sender: string | null
  raw_text: string
  cleaned_text: string | null
  status: string
  created_at: string | null
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`[${res.status}] ${text}`)
  }
  return res.json() as Promise<T>
}

// ─── Ingestion ────────────────────────────────────────────────────────────────

/** Upload a WhatsApp export file (.txt / .zip / .rar). */
export async function uploadFile(file: File): Promise<IngestResponse> {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${BASE_URL}/ingest/`, { method: "POST", body: form })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`[${res.status}] ${text}`)
  }
  return res.json() as Promise<IngestResponse>
}

/** Poll the task-status endpoint once. */
export async function fetchTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  return request<TaskStatusResponse>(`/ingest/status/${taskId}`)
}

/**
 * Poll until the pipeline is done or *timeoutMs* elapses.
 * Resolves with the final TaskStatusResponse.
 * Rejects on FAILED status or timeout.
 */
export async function pollUntilDone(
  taskId: string,
  intervalMs = 2000,
  timeoutMs = 300_000,
): Promise<TaskStatusResponse> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const result = await fetchTaskStatus(taskId)
    if (result.status === "COMPLETED") return result
    if (result.status === "FAILED") throw new Error(result.error ?? "Task failed")
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  throw new Error("Pipeline polling timed out")
}

// ─── Chat ────────────────────────────────────────────────────────────────────

export async function sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>("/chat/", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function fetchSource(chunkId: string): Promise<SourceResponse> {
  return request<SourceResponse>(`/chat/source/${chunkId}`)
}