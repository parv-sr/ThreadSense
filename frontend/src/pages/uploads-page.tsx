import { useState } from 'react'
import { CheckCircle2, Loader2 } from 'lucide-react'
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
        <h1 className='text-2xl font-semibold'>Uploads</h1>
        <p className='text-sm text-slate-400'>Ingest new conversation exports and track deduplication.</p>
      </div>
      <UploadDropzone onFileSelect={handleUpload} />

      <div className='grid gap-4 md:grid-cols-2'>
        <Card className='p-4'>
          <p className='text-sm text-slate-400'>Unique uploads</p>
          <p className='text-3xl font-bold text-emerald-400'>{stats.uploaded}</p>
        </Card>
        <Card className='p-4'>
          <p className='text-sm text-slate-400'>Duplicates skipped</p>
          <p className='text-3xl font-bold text-amber-300'>{stats.duplicates}</p>
        </Card>
      </div>

      <Card className='p-4'>
        <h2 className='mb-3 text-lg font-semibold'>Recent Upload Activity</h2>
        {ingestMutation.isPending && <Loader2 className='h-4 w-4 animate-spin text-emerald-400' />}
        {events.length === 0 ? (
          <p className='text-sm text-slate-400'>No uploads yet.</p>
        ) : (
          <div className='space-y-2'>
            {events.map((event) => (
              <div key={event.id} className='flex items-center justify-between rounded-md bg-slate-800/70 p-3 text-sm'>
                <span>{event.name}</span>
                <span className='flex items-center gap-2 text-slate-300'><CheckCircle2 className='h-4 w-4 text-emerald-400' /> {event.status}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </section>
  )
}
