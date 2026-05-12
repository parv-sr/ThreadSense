import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { format } from 'date-fns'
import { Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { Card } from '@/components/ui/card'
import { parseDedupeStats, useDeleteUploadMutation, useUploadDetailQuery } from '@/lib/api'
import { useUploadStream } from '@/hooks/useUploadStream'

const STAT_LABELS: Record<string, string> = {
  total_messages: 'Total Messages',
  created_chunks: 'Unique Chunks Created',
  duplicates_removed: 'Duplicates Removed',
  system_filtered: 'System Msgs Filtered',
  keyword_filtered: 'Keyword Filtered',
  local_duplicates: 'In-Chat Duplicates',
  batch_duplicates: 'Cross-Batch Duplicates',
  db_duplicates: 'Cross-File Duplicates',
  media_count: 'Media Messages',
  parser_failures: 'Parser Failures',
  final_unique_chunks: 'Final Unique Chunks',
  ignored_chunks: 'Ignored Chunks',
}

export const FileDetailsPage = () => {
  const { rawfileId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: detailData, isLoading } = useUploadDetailQuery(rawfileId)
  const streamState = useUploadStream(rawfileId)
  const deleteMutation = useDeleteUploadMutation()
  const [logLines, setLogLines] = useState<string[]>(['Waiting for processing events...'])
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    setLogLines(['Waiting for processing events...'])
  }, [rawfileId])

  const status = streamState.snapshot?.upload?.progress?.status
                 ?? detailData?.upload?.progress?.status
                 ?? detailData?.upload?.status
                 ?? 'PENDING'
  const progress = streamState.snapshot?.upload?.progress?.percentage
                   ?? detailData?.upload?.progress?.percentage
                   ?? 8
  const upload = streamState.snapshot?.upload ?? detailData?.upload
  const insights = streamState.snapshot?.insights ?? detailData?.insights
  const isTerminal = status === 'COMPLETED' || status === 'FAILED'

  const dedupeStats = upload?.dedupeStats ? parseDedupeStats(upload.dedupeStats) : null
  const hasStats = dedupeStats && dedupeStats.total_messages > 0

  useEffect(() => {
    const msg = streamState.snapshot?.upload?.progress?.message
    if (msg) {
      setLogLines(prev => {
        const next = [...prev, msg]
        if (next.length > 100) return next.slice(next.length - 100)
        return next
      })
    }
  }, [streamState.snapshot])

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync(rawfileId)
      toast.success('File deleted successfully.')
      queryClient.invalidateQueries({ queryKey: ['uploads'] })
      navigate('/uploads')
    } catch {
      toast.error('Failed to delete file.')
    }
  }

  if (isLoading) {
    return <div className="p-8 text-center text-zinc-400">Loading upload details...</div>
  }

  return (
    <section className='space-y-6'>
      <Card className='p-5'>
        <div className='flex items-start justify-between'>
          <div>
            <p className='text-xs uppercase tracking-wider text-zinc-500'>· File Metadata</p>
            <h1 className='mt-2 text-2xl font-semibold'>{upload?.fileName ?? `Upload ${rawfileId}`}</h1>
          </div>
          {confirmDelete ? (
            <div className='flex items-center gap-2'>
              <span className='text-sm text-red-400'>Delete permanently?</span>
              <button
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className='rounded-md bg-red-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-red-500 disabled:opacity-50'
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Confirm'}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className='rounded-md border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800'
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className='flex items-center gap-1.5 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 transition hover:bg-red-500/20'
            >
              <Trash2 className='h-3.5 w-3.5' />
              Delete File
            </button>
          )}
        </div>
        <div className='mt-4 grid gap-3 md:grid-cols-3'>
          <div className='tactile-subtle rounded-xl p-3'>
            <p className='text-xs text-zinc-400'>Upload Time</p>
            <p className='font-mono-data text-sm text-zinc-200'>
              {upload?.uploadedAt ? format(new Date(upload.uploadedAt), 'PPpp') : 'Unavailable'}
            </p>
          </div>
          <div className='tactile-subtle rounded-xl p-3'>
            <p className='text-xs text-zinc-400'>Source</p>
            <p className='font-mono-data text-sm text-zinc-200'>{upload?.source ?? 'N/A'}</p>
          </div>
          <div className='tactile-subtle rounded-xl p-3'>
            <p className='text-xs text-zinc-400'>Raw File ID</p>
            <p className='font-mono-data text-sm text-zinc-200'>{rawfileId}</p>
          </div>
        </div>
      </Card>

      <Card className='p-5'>
        <p className='text-xs uppercase tracking-wider text-zinc-500'>· Live Processing</p>

        <div className='mt-2 flex items-center justify-between'>
          <p className='text-sm text-zinc-300'>Overall Status</p>
          {(status === 'PROCESSED' || status === 'COMPLETED') ? (
              <span className="rounded-full bg-emerald-950 px-3 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500">
                ✅ COMPLETED
              </span>
          ) : status === 'FAILED' ? (
              <span className="rounded-full bg-red-950 px-3 py-1 text-xs font-semibold text-red-400 border border-red-500">
                ❌ FAILED
              </span>
          ) : (
            <span className="rounded-full bg-blue-950 px-3 py-1 text-xs font-semibold text-blue-400 border border-blue-500 animate-pulse">
              {status}
            </span>
          )}
        </div>

        <div className='mt-2 flex items-center justify-between'>
          <p className='text-sm text-zinc-300'>Progress</p>
          <div className="font-mono-data text-xl font-bold text-cyan-300">{progress}%</div>
        </div>

        <div className='mt-3 h-1 w-full overflow-hidden rounded bg-zinc-800'>
          <div className='h-full bg-cyan-400 transition-all duration-300 shadow-[0_0_10px_rgba(34,211,238,0.5)]' style={{ width: `${progress}%` }} />
        </div>

        {streamState.error && (
          <div className='mt-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300'>
            Stream error: {streamState.error}
          </div>
        )}

        {streamState.isDone && (
          <div className='mt-2 text-sm text-emerald-400 font-semibold'>Processing complete.</div>
        )}

        <div className='mt-4 max-h-[300px] overflow-auto rounded-xl border border-zinc-800 bg-black p-4'>
            {logLines.map((line, index) => (
              <p key={`${line}-${index}`} className='font-mono-data text-xs leading-5 text-zinc-300'>
                {line}
              </p>
            ))}
        </div>
      </Card>

      <Card className='p-5'>
        <p className='text-xs uppercase tracking-wider text-zinc-500'>· Processed Data Summary</p>
        <div className='mt-4'>
            {insights ? (
              <div className="space-y-4">
                <div>
                  <h3 className="text-zinc-100 font-semibold">{insights.headline}</h3>
                  <p className="text-zinc-400 text-sm mt-1">{insights.subheadline}</p>
                </div>
                {insights.highlights && insights.highlights.length > 0 && (
                  <ul className="space-y-1">
                    {insights.highlights.map((h: string, i: number) => (
                      <li key={i} className="text-sm text-zinc-300">• {h}</li>
                    ))}
                  </ul>
                )}
                <div className="flex gap-2">
                  <span className="bg-zinc-800 px-2 py-1 rounded text-xs text-zinc-300">
                    {insights.status_summary}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-zinc-500">Insights data will be available once processing completes.</p>
            )}
        </div>
      </Card>

      {isTerminal && hasStats && (
        <Card className='p-5'>
          <p className='text-xs uppercase tracking-wider text-zinc-500'>· Dedupe Statistics</p>
          <p className='mt-1 text-sm text-zinc-400'>Message deduplication and filtering breakdown from the ingestion pipeline.</p>
          <div className='mt-4 grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4'>
            {Object.entries(STAT_LABELS).map(([key, label]) => {
              const value = dedupeStats[key as keyof typeof dedupeStats]
              if (typeof value !== 'number') return null
              return (
                <div key={key} className='rounded-xl border border-zinc-800 bg-zinc-900/50 p-3'>
                  <p className='text-xs text-zinc-500'>{label}</p>
                  <p className='font-mono-data mt-1 text-lg font-bold text-zinc-100'>{value.toLocaleString()}</p>
                </div>
              )
            })}
          </div>
          {dedupeStats.notes && dedupeStats.notes.length > 0 && (
            <div className='mt-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3'>
              <p className='text-xs font-medium text-amber-400'>Notes</p>
              {dedupeStats.notes.map((note, i) => (
                <p key={i} className='mt-1 text-xs text-zinc-400'>{note}</p>
              ))}
            </div>
          )}
        </Card>
      )}
    </section>
  )
}
