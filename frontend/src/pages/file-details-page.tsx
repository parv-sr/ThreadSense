import { useEffect, useMemo, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { format } from 'date-fns'
import { Card } from '@/components/ui/card'
import { parseDedupeStats, type DedupeStats, type UploadRecord, useTaskStatusQuery } from '@/lib/api'

//Helpers

const isAllDuplicates = (dedupe: any): boolean => {
  if (!dedupe) return false
  return(
    dedupe.total_messages > 0 &&
    dedupe.final_unique_chunks === 0
  )
}

const STORAGE_KEY = 'threadsense.uploads'

const metricCards: Array<{ key: keyof DedupeStats; label: string; emphasis?: boolean }> = [
  { key: 'total_messages', label: 'Total Messages', emphasis: true },
  { key: 'system_filtered', label: 'System Filtered' },
  { key: 'media_count', label: 'Media Count' },
  { key: 'keyword_filtered', label: 'Keyword Filtered' },
  { key: 'local_duplicates', label: 'Local Duplicates' },
  { key: 'batch_duplicates', label: 'Batch Duplicates' },
  { key: 'db_duplicates', label: 'DB Duplicates' },
  { key: 'duplicates_removed', label: 'Duplicates Removed' },
  { key: 'final_unique_chunks', label: 'Final Unique Chunks', emphasis: true },
  { key: 'created_chunks', label: 'Created Chunks' },
  { key: 'ignored_chunks', label: 'Ignored Chunks' },
  { key: 'parser_failures', label: 'Parser Failures' },
]

export const FileDetailsPage = () => {
  const { rawfileId = '' } = useParams()
  const location = useLocation()
  const uploadFromState = (location.state as { upload?: UploadRecord } | null)?.upload
  const [upload, setUpload] = useState<UploadRecord | null>(uploadFromState ?? null)
  const [status, setStatus] = useState<string>(uploadFromState?.status ?? 'PENDING')
  const [logLines, setLogLines] = useState<string[]>(['Waiting for processing events...'])
  const [progress, setProgress] = useState<number>(8)

  useEffect(() => {
    if (upload) return
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    try {
      const list = JSON.parse(raw) as UploadRecord[]
      const match = list.find((item) => item.rawfileId === rawfileId)
      if (match) {
        setUpload(match)
        setStatus(match.status)
      }
    } catch {
      setUpload(null)
    }
  }, [rawfileId, upload])

  const { data: taskData } = useTaskStatusQuery(upload?.taskId, status !== 'COMPLETED' && status !== 'FAILED')

  useEffect(() => {
    if (taskData) {
      if (taskData.status) setStatus(taskData.status)
      if (typeof taskData.progress_percentage === 'number') {
        setProgress(Math.max(2, Math.min(100, taskData.progress_percentage)))
      }
      if (taskData.result?.dedupe_stats) {
        setUpload((prev) => (prev ? { ...prev, dedupeStats: parseDedupeStats(taskData.result?.dedupe_stats) } : prev))
      }
      if (taskData.result?.notes) {
        setLogLines([String(taskData.result.notes)])
      }
    }
  }, [taskData])

  const dedupe = useMemo(() => parseDedupeStats(upload?.dedupeStats), [upload?.dedupeStats])

  return (
    <section className='space-y-6'>
      <Card className='p-5'>
        <p className='text-xs uppercase tracking-wider text-zinc-500'>Section A · File Metadata</p>
        <h1 className='mt-2 text-2xl font-semibold'>{upload?.name ?? `Upload ${rawfileId}`}</h1>
        <div className='mt-4 grid gap-3 md:grid-cols-3'>
          <div className='tactile-subtle rounded-xl p-3'>
            <p className='text-xs text-zinc-400'>Upload Time</p>
            <p className='font-mono-data text-sm text-zinc-200'>
              {upload?.uploadedAt ? format(new Date(upload.uploadedAt), 'PPpp') : 'Unavailable'}
            </p>
          </div>
          <div className='tactile-subtle rounded-xl p-3'>
            <p className='text-xs text-zinc-400'>File Size</p>
            <p className='font-mono-data text-sm text-zinc-200'>{upload?.fileSize?.toLocaleString() ?? 0} bytes</p>
          </div>
          <div className='tactile-subtle rounded-xl p-3'>
            <p className='text-xs text-zinc-400'>Raw File ID</p>
            <p className='font-mono-data text-sm text-zinc-200'>{rawfileId}</p>
          </div>
        </div>
      </Card>

      <Card className='p-5'>
        <p className='text-xs uppercase tracking-wider text-zinc-500'>Section B · Live Processing</p>

        {/* Smart status header */}
        <div className='mt-2 flex items-center justify-between'>
          <p className='text-sm text-zinc-300'>Overall Status</p>
          {(status === 'PROCESSED' || status === 'COMPLETED') ? (
            isAllDuplicates(dedupe) ? (
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-emerald-950 px-3 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500 flex items-center gap-1">
                  ✅ COMPLETED
                </span>
                <span className="rounded-full bg-amber-950 px-3 py-1 text-xs font-semibold text-amber-400 border border-amber-500">
                  ALL DUPLICATES
                </span>
              </div>
            ) : (
              <span className="rounded-full bg-emerald-950 px-3 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500">
                ✅ COMPLETED
              </span>
            )
          ) : (
            <span className="rounded-full bg-blue-950 px-3 py-1 text-xs font-semibold text-blue-400 border border-blue-500 animate-pulse">
              {status}
            </span>
          )}
        </div>

        <div className='mt-2 flex items-center justify-between'>
          <p className='text-sm text-zinc-300'>Overall Status</p>
          <div className="font-mono-data text-xl font-bold text-cyan-300">{progress}%</div>
        </div>

        <div className='mt-3 h-1 w-full overflow-hidden rounded bg-zinc-800'>
          <div className='h-full bg-cyan-400 transition-all duration-300 shadow-[0_0_10px_rgba(34,211,238,0.5)]' style={{ width: `${progress}%` }} />
        </div>

        {/* Live area — now smart about duplicates */}
        <div className='mt-4 max-h-[300px] overflow-auto rounded-xl border border-zinc-800 bg-black p-4'>
          {dedupe && isAllDuplicates(dedupe) ? (
            <div className="flex gap-6">
              <div className="text-6xl">🎉</div>
              <div className="flex-1">
                <h3 className="text-emerald-300 text-xl font-semibold">
                  Every message was already in your knowledge base
                </h3>
                <p className="text-zinc-300 mt-3">
                  All{' '}
                  <span className="font-mono bg-emerald-900/80 px-2 py-0.5 rounded text-emerald-400">
                    {dedupe.total_messages}
                  </span>{' '}
                  messages were duplicates.
                </p>
                <p className="text-zinc-400 mt-6 text-sm">
                  File ingested successfully — no new chunks added.<br />
                  Your workspace stays clean ✨
                </p>
              </div>
            </div>
          ) : (
            /* Normal live log (exactly as before) */
            logLines.map((line, index) => (
              <p key={`${line}-${index}`} className='font-mono-data text-xs leading-5 text-zinc-300'>
                {line}
              </p>
            ))
          )}
        </div>
      </Card>

      <Card className='p-5'>
        <p className='text-xs uppercase tracking-wider text-zinc-500'>Section C · Deduplication Stats</p>
        <div className='mt-4 grid gap-3 md:grid-cols-3'>
          {metricCards.map((metric) => (
            <div
              key={metric.key}
              className={`rounded-xl border p-4 ${
                metric.key === 'final_unique_chunks'
                  ? 'border-cyan-500/60 bg-zinc-900'
                  : metric.emphasis
                    ? 'border-zinc-700 bg-zinc-900'
                    : 'border-zinc-800 bg-zinc-950'
              }`}
            >
              <p className='text-xs uppercase tracking-wide text-zinc-500'>{metric.label}</p>
              <p className={`font-mono-data mt-2 text-2xl ${metric.key === 'final_unique_chunks' ? 'text-cyan-300' : 'text-zinc-100'}`}>
                {dedupe[metric.key].toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      </Card>
    </section>
  )
}
