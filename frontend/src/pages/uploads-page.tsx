import { useState } from 'react'
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { toast } from 'sonner'
import { UploadDropzone } from '@/components/upload/upload-dropzone'
import { Card } from '@/components/ui/card'
import { useIngestMutation } from '@/lib/api'

interface UploadEvent {
  id: string
  name: string
  status: string
  time: string
}

export const UploadsPage = () => {
  const ingestMutation = useIngestMutation()
  const [events, setEvents] = useState<UploadEvent[]>([])
  const [stats, setStats] = useState({ uploaded: 0, duplicates: 0 })

  const handleUpload = async (file: File) => {
    try {
      const result = await ingestMutation.mutateAsync(file)
      setEvents((prev) => [{ id: crypto.randomUUID(), name: file.name, status: result.status, time: new Date().toISOString() }, ...prev])
      setStats((prev) => ({
        uploaded: prev.uploaded + (result.status === 'ALREADY_EXISTS' ? 0 : 1),
        duplicates: prev.duplicates + (result.status === 'ALREADY_EXISTS' ? 1 : 0),
      }))
      toast.success(result.status === 'ALREADY_EXISTS' ? 'Duplicate file detected.' : 'Upload queued successfully.')
    } catch {
      toast.error('Upload failed. Please try again.')
    }
  }

  return (
    <section className='space-y-6'>
      <div>
        <h1 className='text-2xl font-semibold tracking-tight'>Uploads</h1>
        <p className='text-sm text-slate-400'>Ingest conversation exports and track deduplication in real time.</p>
      </div>

      <UploadDropzone onFileSelect={handleUpload} />

      {ingestMutation.isError ? (
        <div className='flex items-center gap-2 rounded-xl border border-red-400/20 bg-red-500/10 px-3 py-2 text-sm text-red-200'>
          <AlertTriangle className='h-4 w-4' /> Could not call /ingest/. Please verify API availability.
        </div>
      ) : null}

      <div className='grid gap-4 md:grid-cols-2'>
        <Card className='p-4'>
          <p className='text-sm text-slate-400'>Unique uploads</p>
          <p className='text-3xl font-bold text-emerald-300'>{stats.uploaded}</p>
        </Card>
        <Card className='p-4'>
          <p className='text-sm text-slate-400'>Duplicates skipped</p>
          <p className='text-3xl font-bold text-amber-300'>{stats.duplicates}</p>
        </Card>
      </div>

      <Card className='p-4'>
        <h2 className='mb-3 text-lg font-semibold'>Recent Upload Activity</h2>
        {ingestMutation.isPending ? <Loader2 className='h-4 w-4 animate-spin text-cyan-200' /> : null}
        {events.length === 0 ? (
          <p className='text-sm text-slate-400'>No uploads yet.</p>
        ) : (
          <div className='space-y-2'>
            {events.map((event) => (
              <div key={event.id} className='glass-muted flex items-center justify-between rounded-xl p-3 text-sm transition hover:-translate-y-0.5'>
                <span className='truncate pr-3'>{event.name}</span>
                <span className='flex shrink-0 items-center gap-2 text-slate-300'>
                  <CheckCircle2 className='h-4 w-4 text-emerald-300' />
                  {event.status} · {formatDistanceToNow(new Date(event.time), { addSuffix: true })}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </section>
  )
}
