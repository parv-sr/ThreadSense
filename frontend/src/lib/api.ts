import axios, { type AxiosProgressEvent } from 'axios'
import { useMutation, useQuery } from '@tanstack/react-query'
import { supabase } from './supabase'
import { env } from './env'
import { toast } from 'sonner'
import type {
  ChatPayload,
  ChatResponse,
  IngestResponse,
  SourceChunk,
  TaskStatusResponse,
  UploadSummary,
  UploadDetail,
  DedupeStats,
} from '../types/api'

// ─── Axios instance ───────────────────────────────────────────────────────────

export const api = axios.create({
  baseURL: env.apiUrl,
  timeout: 30_000,
})

// Attach the Supabase session token to every request.
// If there is no session, skip silently — public routes still work.
api.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

// Track whether a sign-out redirect is already in progress so we only fire once.
let _signingOut = false

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      if (!_signingOut) {
        _signingOut = true
        console.warn('[ThreadSense] 401 received — session invalid, signing out.')
        await supabase.auth.signOut()
        window.location.replace('/settings')
      }
    } else {
      // Only show a toast for unexpected server errors, not auth failures.
      const msg: string =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        'An unexpected error occurred'
      toast.error(msg, { id: msg }) // `id` deduplicates identical toasts
    }
    return Promise.reject(error)
  }
)

// ─── DedupeStats helpers ──────────────────────────────────────────────────────

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
    notes: Array.isArray(source.notes) ? source.notes.map((e) => String(e)) : [],
  }
}

// ─── Mutations ────────────────────────────────────────────────────────────────

export const useChatMutation = () =>
  useMutation({
    mutationFn: async (payload: ChatPayload) => {
      const { data } = await api.post<ChatResponse>('/chat/', payload)
      return data
    },
  })

export const useIngestMutation = () =>
  useMutation({
    mutationFn: async ({
      file,
      onUploadProgress,
    }: {
      file: File
      onUploadProgress?: (progressEvent: AxiosProgressEvent) => void
    }) => {
      const formData = new FormData()
      formData.append('file', file)
      const { data } = await api.post<IngestResponse>('/ingest/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress,
      })
      return data
    },
  })

// ─── Queries ──────────────────────────────────────────────────────────────────

/** Poll task status every 4 s, stopping when terminal. */
export const useTaskStatusQuery = (taskId?: string, enabled = true) =>
  useQuery({
    queryKey: ['task-status', taskId],
    enabled: Boolean(taskId) && enabled,
    refetchInterval: (query) => {
      const s = query.state.data?.status
      if (s === 'COMPLETED' || s === 'FAILED') return false
      return 4_000
    },
    refetchIntervalInBackground: false,
    queryFn: async () => {
      const { data } = await api.get<TaskStatusResponse>(`/ingest/status/${taskId}`)
      return data
    },
  })

/**
 * Upload list — no automatic background polling.
 * The page can call `refetch()` explicitly after an upload completes,
 * or the user can navigate away and back to refresh.
 */
export const useUploadsQuery = () =>
  useQuery({
    queryKey: ['uploads'],
    queryFn: async () => {
      const { data } = await api.get('/ingest/uploads')
      return data.uploads as UploadSummary[]
    },
    staleTime: 30_000,   // treat data fresh for 30 s
    refetchOnWindowFocus: true, // refetch when user returns to tab
  })

/** Single upload detail — no polling; real-time updates come via SSE. */
export const useUploadDetailQuery = (rawfileId: string | undefined) =>
  useQuery({
    queryKey: ['upload-detail', rawfileId],
    enabled: Boolean(rawfileId),
    queryFn: async () => {
      const { data } = await api.get(`/ingest/uploads/${rawfileId}`)
      return data as UploadDetail
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
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