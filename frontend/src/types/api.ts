// Corresponds to: _build_progress_payload() in backend/src/api/endpoints/ingestion.py
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

// Corresponds to: _fetch_upload_detail_payload() → listings[] in backend/src/api/endpoints/ingestion.py
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

// Corresponds to: GET /ingest/uploads → uploads[] in backend/src/api/endpoints/ingestion.py
export interface UploadSummary {
  rawfileId: string
  fileName: string
  status: string
  processed: boolean
  uploadedAt: string
  processStartedAt: string | null
  processFinishedAt: string | null
  notes: string | null
  source: string | null
  taskId: string | null
  dedupeStats: Record<string, unknown>
  progress: ProgressPayload
  listingsCount: number
  averageConfidence: number | null
}

// Corresponds to: GET /ingest/uploads/{rawfileId} in backend/src/api/endpoints/ingestion.py
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

// Corresponds to: POST /chat/ request body
export interface ChatPayload {
  message: string
  thread_id?: string
}

// Corresponds to: POST /chat/ response
export interface ChatResponse {
  table_html: string
  reasoning: string
  sources: string[]
}

// Corresponds to: POST /ingest/ response
export interface IngestResponse {
  task_id: string
  rawfile_id: string
  status: 'QUEUED' | 'ALREADY_EXISTS' | string
}

// Corresponds to: GET /chat/source/{chunkId} response
export interface SourceChunk {
  chunk_id: string
  message_start: string | null
  sender: string | null
  raw_text: string
  cleaned_text: string | null
  status: string
  created_at: string | null
}

// Corresponds to: GET /ingest/status/{task_id} response
export interface TaskStatusResponse {
  status: 'PENDING' | 'COMPLETED' | 'FAILED' | 'PROCESSING' | string
  task_id: string
  progress_percentage?: number
  result?: Record<string, unknown>
  error?: string
}

// Corresponds to: dedupe_stats dict from backend DedupeStats dataclass
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
