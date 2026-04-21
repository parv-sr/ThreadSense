export interface ProgressPayload {
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  percentage: number
  stage: string
  message: string
  terminal: boolean
  should_poll: boolean
  chunks_total: number
  chunks_processed: number
  chunks_failed: number
  listings_extracted: number
}

export interface ListingItem {
  id: string
  rawChunkId: string
  sender: string | null
  timestamp: string | null
  propertyType: string
  transactionType: string
  listingIntent: string
  location: string | null
  price: number | null
  bhk: number | null
  areaSqft: number | null
  furnished: string | null
  landmark: string | null
  contactNumber: string | null
  isVerified: boolean
  status: string
  confidenceScore: number
  excerpt: string
}

export interface UploadSummary {
  id: string
  rawfile_id: string
  name: string
  status: string
  uploaded_at: string
  task_id: string
  file_size: number
}

export interface UploadDetail {
  upload: UploadSummary
  insights: {
    headline: string
    subheadline: string
    highlights: string[]
    status_summary: string
    listings: ListingItem[]
  }
  streamedAt: string
}

export interface ChatPayload {
  message: string
  thread_id?: string
}

export interface ChatResponse {
  table_html: string
  reasoning: string
  sources: string[]
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
  progress_percentage?: number
  result?: Record<string, unknown>
  error?: string
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
