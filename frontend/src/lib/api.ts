import axios from 'axios'
import { useMutation, useQuery } from '@tanstack/react-query'
import { z } from 'zod'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
})

const chatResponseSchema = z.object({
  table_html: z.string(),
  reasoning: z.string(),
  sources: z.array(z.string()),
})

export type ChatResponse = z.infer<typeof chatResponseSchema>

export interface ChatPayload {
  message: string
  thread_id?: string
}

export interface IngestResponse {
  task_id: string
  rawfile_id: string
  status: 'QUEUED' | 'ALREADY_EXISTS' | string
}

export interface SourceChunk {
  chunk_id: string
  message_start: string | null
  sender: string | null
  raw_text: string
  cleaned_text: string | null
  status: string
  created_at: string | null
}

export interface TaskStatusResponse {
  status: 'PENDING' | 'COMPLETED' | 'FAILED' | 'PROCESSING' | string
  task_id: string
  result?: Record<string, unknown>
  error?: string
}

export interface UploadRecord {
  id: string
  name: string
  status: string
  uploadedAt: string
  taskId: string
  rawfileId: string
  fileSize: number
  dedupeStats?: DedupeStats
}

export interface DedupeStats {
  total_messages: number
  system_filtered: number
  media_count: number
  keyword_filtered: number
  local_duplicates: number
  batch_duplicates: number
  db_duplicates: number
  duplicates_removed: number
  final_unique_chunks: number
  created_chunks: number
  ignored_chunks: number
  parser_failures: number
  notes: string[]
}

const DEDUPE_DEFAULTS: DedupeStats = {
  total_messages: 0,
  system_filtered: 0,
  media_count: 0,
  keyword_filtered: 0,
  local_duplicates: 0,
  batch_duplicates: 0,
  db_duplicates: 0,
  duplicates_removed: 0,
  final_unique_chunks: 0,
  created_chunks: 0,
  ignored_chunks: 0,
  parser_failures: 0,
  notes: [],
}

export const parseDedupeStats = (value: unknown): DedupeStats => {
  if (!value || typeof value !== 'object') return DEDUPE_DEFAULTS
  const source = value as Record<string, unknown>

  return {
    ...DEDUPE_DEFAULTS,
    total_messages: Number(source.total_messages ?? 0),
    system_filtered: Number(source.system_filtered ?? 0),
    media_count: Number(source.media_count ?? 0),
    keyword_filtered: Number(source.keyword_filtered ?? 0),
    local_duplicates: Number(source.local_duplicates ?? 0),
    batch_duplicates: Number(source.batch_duplicates ?? 0),
    db_duplicates: Number(source.db_duplicates ?? 0),
    duplicates_removed: Number(source.duplicates_removed ?? 0),
    final_unique_chunks: Number(source.final_unique_chunks ?? 0),
    created_chunks: Number(source.created_chunks ?? 0),
    ignored_chunks: Number(source.ignored_chunks ?? 0),
    parser_failures: Number(source.parser_failures ?? 0),
    notes: Array.isArray(source.notes) ? source.notes.map((entry) => String(entry)) : [],
  }
}

export const createProcessingEventSource = (taskId: string): EventSource => {
  const streamPath = import.meta.env.VITE_SSE_PATH ?? '/ingest/stream'
  const normalized = streamPath.startsWith('/') ? streamPath : `/${streamPath}`
  const url = `${API_BASE_URL}${normalized}/${taskId}`
  return new EventSource(url)
}

export const useChatMutation = () =>
  useMutation({
    mutationFn: async (payload: ChatPayload) => {
      const { data } = await api.post('/chat/', payload)
      return chatResponseSchema.parse(data)
    },
  })

export const useIngestMutation = () =>
  useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const { data } = await api.post<IngestResponse>('/ingest/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return data
    },
  })

export const useTaskStatusQuery = (taskId?: string, enabled = true) =>
  useQuery({
    queryKey: ['task-status', taskId],
    enabled: Boolean(taskId) && enabled,
    refetchInterval: 4_000,
    queryFn: async () => {
      const { data } = await api.get<TaskStatusResponse>(`/ingest/status/${taskId}`)
      return data
    },
  })

export const useSourceQuery = (chunkId?: string, enabled = true) =>
  useQuery({
    queryKey: ['source', chunkId],
    enabled: Boolean(chunkId) && enabled,
    queryFn: async () => {
      const { data } = await api.get<SourceChunk>(`/chat/source/${chunkId}`)
      return data
    },
  })