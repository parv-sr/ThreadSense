import axios, { type AxiosProgressEvent } from 'axios'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { env } from './env'
import type {
  ChatPayload,
  ChatResponse,
  DedupeStats,
  IngestResponse,
  ListingFacets,
  ListingsQuery,
  ListingsResponse,
  SourceChunk,
  TaskStatusResponse,
  UploadDetail,
  UploadSummary,
} from '../types/api'

export const api = axios.create({
  baseURL: env.apiUrl,
  timeout: 30_000,
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const msg: string =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An unexpected error occurred'
    toast.error(msg, { id: msg })
    return Promise.reject(error)
  },
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
    notes: Array.isArray(source.notes) ? source.notes.map((e) => String(e)) : [],
  }
}

export const useChatMutation = () =>
  useMutation({
    mutationFn: async (payload: ChatPayload) => {
      const { data } = await api.post<ChatResponse>('/chat', payload)
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

export const useFacetsQuery = () =>
  useQuery({
    queryKey: ['listing-facets'],
    queryFn: async () => {
      const { data } = await api.get<ListingFacets>('/listings/facets')
      return data
    },
    staleTime: 20_000,
  })

export const useListingsQuery = (query: ListingsQuery) =>
  useQuery({
    queryKey: ['listings', query],
    queryFn: async () => {
      const params = new URLSearchParams()
      Object.entries(query).forEach(([key, value]) => {
        if (value === undefined || value === null || value === '') return
        if (Array.isArray(value)) {
          value.forEach((item) => params.append(key, String(item)))
        } else {
          params.set(key, String(value))
        }
      })
      const { data } = await api.get<ListingsResponse>(`/listings?${params.toString()}`)
      return data
    },
    placeholderData: (previous) => previous,
  })

export const useDeleteListingsMutation = () =>
  useMutation({
    mutationFn: async (ids: string[]) => {
      const { data } = await api.post<{ deleted: number }>('/listings/delete', { ids })
      return data
    },
  })

export const useDeleteUploadMutation = () =>
  useMutation({
    mutationFn: async (rawfileId: string) => {
      const { data } = await api.delete<{ deleted: boolean; rawfileId: string; fileName: string }>(
        `/ingest/uploads/${rawfileId}`,
      )
      return data
    },
  })

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

export const useUploadsQuery = () =>
  useQuery({
    queryKey: ['uploads'],
    queryFn: async () => {
      const { data } = await api.get('/ingest/uploads')
      return data.uploads as UploadSummary[]
    },
    staleTime: 10_000,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const uploads = query.state.data
      if (!uploads) return 15_000
      const hasActive = uploads.some((u) => !u.progress.terminal)
      return hasActive ? 8_000 : false
    },
    refetchIntervalInBackground: false,
  })

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

export const useSourceQuery = (listingId?: string, enabled = true) =>
  useQuery({
    queryKey: ['source', listingId],
    enabled: Boolean(listingId) && enabled,
    queryFn: async () => {
      const { data } = await api.get<SourceChunk>(`/chat/source/${listingId}`)
      return data
    },
  })
