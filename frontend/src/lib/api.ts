import axios from 'axios'
import { useMutation, useQuery } from '@tanstack/react-query'
import { z } from 'zod'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

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
  message_start: string
  sender: string
  raw_text: string
  cleaned_text: string
  status: string
  created_at: string
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

export const useSourceQuery = (chunkId?: string, enabled = true) =>
  useQuery({
    queryKey: ['source', chunkId],
    enabled: Boolean(chunkId) && enabled,
    queryFn: async () => {
      const { data } = await api.get<SourceChunk>(`/source/${chunkId}`)
      return data
    },
  })
