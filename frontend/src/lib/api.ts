import axios from 'axios'
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
  DedupeStats
} from '../types/api'

export const api = axios.create({
  baseURL: env.apiUrl,
  timeout: 30_000,
})

api.interceptors.request.use(async (config) => {
  const { data: { session }, error } = await supabase.auth.getSession()
  if (error || !session) {
    // Attempt refresh before giving up
    const { data: refreshed } = await supabase.auth.refreshSession()
    if (refreshed.session?.access_token) {
      config.headers.Authorization = `Bearer ${refreshed.session.access_token}`
    }
  } else if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      supabase.auth.signOut().then(() => {
        window.location.href = '/settings'
      })
    } else {
      toast.error(error.response?.data?.message || 'An unexpected error occurred')
    }
    return Promise.reject(error)
  }
)

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

export const useChatMutation = () =>
  useMutation({
    mutationFn: async (payload: ChatPayload) => {
      const { data } = await api.post<ChatResponse>('/chat/', payload)
      return data
    },
  })

export const useIngestMutation = () =>
  useMutation({
    mutationFn: async ({ file, onUploadProgress }: { file: File; onUploadProgress?: (progressEvent: any) => void }) => {
      const formData = new FormData()
      formData.append('file', file)
      const { data } = await api.post<IngestResponse>('/ingest/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress,
      })
      return data
    },
  })

export const useTaskStatusQuery = (taskId?: string, enabled = true) =>
  useQuery({
    queryKey: ['task-status', taskId],
    enabled: Boolean(taskId) && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'COMPLETED' || status === 'FAILED') return false
      return 4_000
    },
    refetchIntervalInBackground: false,
    queryFn: async () => {
      const { data } = await api.get<TaskStatusResponse>(`/ingest/status/${taskId}`)
      return data
    },
  })

export const useUploadsQuery = () =>
  useQuery({
    queryKey: ['uploads'],
    queryFn: async () => {
      const { data } = await api.get('/ingest/uploads')
      return data.uploads as UploadSummary[]
    },
    refetchInterval: 8_000,
  })

export const useUploadDetailQuery = (rawfileId: string | undefined) =>
  useQuery({
    queryKey: ['upload-detail', rawfileId],
    enabled: Boolean(rawfileId),
    queryFn: async () => {
      const { data } = await api.get(`/ingest/uploads/${rawfileId}`)
      return data as UploadDetail
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