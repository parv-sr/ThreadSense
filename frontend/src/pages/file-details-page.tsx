import { useEffect, useMemo, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { format } from 'date-fns'
import { Card } from '@/components/ui/card'
import {
  createProcessingEventSource,
  parseDedupeStats,
  useTaskStatusQuery,
  type DedupeStats,
  type UploadRecord,
} from '@/lib/api'

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

  const taskStatusQuery = useTaskStatusQuery(upload?.taskId, Boolean(upload?.taskId))

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

  useEffect(() => {
    const taskStatus = taskStatusQuery.data
    if (!taskStatus) return

    setStatus(taskStatus.status)
    if (taskStatus.status === 'COMPLETED') setProgress(100)

    if (taskStatus.result?.dedupe_stats) {
      setUpload((previous) =>
        previous
          ? {
              ...previous,
              dedupeStats: parseDedupeStats(taskStatus.result?.dedupe_stats),
            }
          : previous,
      )
    }
  }, [taskStatusQuery.data])

  useEffect(() => {
    if (!upload?.taskId) return

    const source = createProcessingEventSource(upload.taskId)

    source.onmessage = (event) => {
      const next = event.data
      setLogLines((previous) => [...previous.slice(-199), next])

      try {
        const parsed = JSON.parse(next) as {
          status?: string
          progress?: number
          message?: string
          dedupe_stats?: unknown
        }

        if (parsed.status) setStatus(parsed.status)
        if (typeof parsed.progress === 'number') {
          setProgress(Math.max(2, Math.min(100, parsed.progress)))
        }

        if (parsed.dedupe_stats) {
          setUpload((previous) =>
            previous
              ? {
                  ...previous,
                  dedupeStats: parseDedupeStats(parsed.dedupe_stats),
                }
              : previous,
          )
        }
      } catch {
        if (next.toLowerCase().includes('completed')) {
          setStatus('COMPLETED')
          setProgress(100)
        }
      }
    }

    source.onerror = () => {
      setLogLines((previous) => [...previous.slice(-199), '[stream] event source disconnected; retry in progress...'])
    }

    return () => {
      source.close()
    }
  }, [upload?.taskId])

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
            <p className='font-mono-data truncate text-sm text-zinc-200'>{rawfileId}</p>
          </div>
        </div>
      </Card>

      <Card className='p-5'>
        <p className='text-xs uppercase tracking-wider text-zinc-500'>Section B · Live Processing</p>
        <div className='mt-2 flex items-center justify-between'>
          <p className='text-sm text-zinc-300'>Overall Status</p>
          <span className='font-mono-data text-sm text-cyan-300'>{status}</span>
        </div>
        <div className='mt-3 h-1 w-full overflow-hidden rounded bg-zinc-800'>
          <div className='h-full bg-cyan-400 transition-all duration-300' style={{ width: `${progress}%` }} />
        </div>
        <div className='mt-4 max-h-[320px] overflow-auto rounded-xl border border-zinc-800 bg-black p-4'>
          {logLines.map((line, index) => (
            <p key={`${line}-${index}`} className='font-mono-data text-xs leading-5 text-zinc-300'>
              {line}
            </p>
          ))}
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
