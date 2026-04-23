import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { format } from 'date-fns'
import { Card } from '@/components/ui/card'
import { useUploadDetailQuery } from '@/lib/api'
import { useUploadStream } from '@/hooks/useUploadStream'

export const FileDetailsPage = () => {
  const { rawfileId = '' } = useParams()
  const { data: detailData, isLoading } = useUploadDetailQuery(rawfileId)
  const streamState = useUploadStream(rawfileId)
  const [logLines, setLogLines] = useState<string[]>(['Waiting for processing events...'])

  // Reset logLines when rawfileId changes
  useEffect(() => {
    setLogLines(['Waiting for processing events...'])
  }, [rawfileId])

  // Derive display values from SSE snapshot → REST fallback, drilling into the correct nested structure
  const status = streamState.snapshot?.upload?.progress?.status
                 ?? detailData?.upload?.progress?.status
                 ?? detailData?.upload?.status
                 ?? 'PENDING'
  const progress = streamState.snapshot?.upload?.progress?.percentage
                   ?? detailData?.upload?.progress?.percentage
                   ?? 8
  const upload = streamState.snapshot?.upload ?? detailData?.upload

  // Derive insights from SSE snapshot for real-time Section C updates
  const insights = streamState.snapshot?.insights ?? detailData?.insights

  // Drive log lines from the SSE snapshot's progress.message field
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

  if (isLoading) {
    return <div className="p-8 text-center text-zinc-400">Loading upload details...</div>
  }

  return (
    <section className='space-y-6'>
      <Card className='p-5'>
        <p className='text-xs uppercase tracking-wider text-zinc-500'>Section A · File Metadata</p>
        <h1 className='mt-2 text-2xl font-semibold'>{upload?.fileName ?? `Upload ${rawfileId}`}</h1>
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
        <p className='text-xs uppercase tracking-wider text-zinc-500'>Section B · Live Processing</p>

        {/* Smart status header */}
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

        {/* Stream error display */}
        {streamState.error && (
          <div className='mt-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300'>
            Stream error: {streamState.error}
          </div>
        )}

        {/* Processing complete badge */}
        {streamState.isDone && (
          <div className='mt-2 text-sm text-emerald-400 font-semibold'>✅ Processing complete.</div>
        )}

        {/* Live area */}
        <div className='mt-4 max-h-[300px] overflow-auto rounded-xl border border-zinc-800 bg-black p-4'>
            {logLines.map((line, index) => (
              <p key={`${line}-${index}`} className='font-mono-data text-xs leading-5 text-zinc-300'>
                {line}
              </p>
            ))}
        </div>
      </Card>

      <Card className='p-5'>
        <p className='text-xs uppercase tracking-wider text-zinc-500'>Section C · Processed Data Summary</p>
        <div className='mt-4'>
            {insights ? (
              <div className="space-y-4">
                <div>
                  <h3 className="text-zinc-100 font-semibold">{insights.headline}</h3>
                  <p className="text-zinc-400 text-sm mt-1">{insights.subheadline}</p>
                </div>
                {insights.highlights && insights.highlights.length > 0 && (
                  <ul className="space-y-1">
                    {insights.highlights.map((h, i) => (
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
    </section>
  )
}
