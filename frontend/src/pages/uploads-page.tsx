import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'
import { Link } from 'react-router-dom'
import { UploadDropzone } from '@/components/upload/upload-dropzone'
import { Card } from '@/components/ui/card'
import { useIngestMutation, type UploadRecord } from '@/lib/api'

const STORAGE_KEY = 'threadsense.uploads'

export const UploadsPage = () => {
  const ingestMutation = useIngestMutation()
  const [uploads, setUploads] = useState<UploadRecord[]>([])

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    try {
      setUploads(JSON.parse(raw) as UploadRecord[])
    } catch {
      setUploads([])
    }
  }, [])

  const persist = (items: UploadRecord[]) => {
    setUploads(items)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
  }

  const handleUpload = async (file: File) => {
    try {
      const result = await ingestMutation.mutateAsync(file)
      const next: UploadRecord[] = [
        {
          id: crypto.randomUUID(),
          name: file.name,
          status: result.status,
          uploadedAt: new Date().toISOString(),
          taskId: result.task_id,
          rawfileId: result.rawfile_id,
          fileSize: file.size,
        },
        ...uploads,
      ]
      persist(next)
      toast.success(result.status === 'ALREADY_EXISTS' ? 'Duplicate file detected.' : 'Upload queued successfully.')
    } catch {
      toast.error('Upload failed. Please try again.')
    }
  }

  const totals = useMemo(
    () => ({
      total: uploads.filter((u) => u.status === 'ALREADY_EXISTS').length,
      uploaded: uploads.filter((u) => u.status !== 'ALREADY_EXISTS').length,
      duplicates: uploads.filter((u) => u.status === 'ALREADY_EXISTS').length,
    }),
    [uploads],
  )

  return (
    <section className='space-y-6'>
      <div>
        <h1 className='text-2xl font-semibold tracking-tight'>Uploads</h1>
        <p className='text-sm text-zinc-400'>Ingest conversation exports and inspect processing pipelines per file.</p>
      </div>

      <UploadDropzone onFileSelect={handleUpload} />

      {ingestMutation.isError ? (
        <div className='flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200'>
          <AlertTriangle className='h-4 w-4' /> Could not call /ingest/. Please verify API availability.
        </div>
      ) : null}

      <div className='grid gap-4 md:grid-cols-3'>
        <Card className='p-4'>
          <p className='text-xs uppercase tracking-wide text-zinc-400'>Total Files</p>
          <p className='font-mono-data mt-2 text-3xl font-bold'>{totals.total}</p>
        </Card>
        <Card className='p-4'>
          <p className='text-sm text-zinc-400'>Unique uploads</p>
          <p className='font-mono-data text-3xl font-bold text-zinc-100'>{totals.uploaded}</p>
        </Card>
        <Card className='p-4'>
          <p className='text-sm text-zinc-400'>Duplicates skipped</p>
          <p className='font-mono-data text-3xl font-bold text-zinc-100'>{totals.duplicates}</p>
        </Card>
      </div>

      <Card className='overflow-hidden p-0'>
        <div className='border-b border-zinc-800 px-4 py-3'>
          <h2 className='text-lg font-semibold'>Upload Registry</h2>
          {ingestMutation.isPending ? <Loader2 className='mt-2 h-4 w-4 animate-spin text-cyan-300' /> : null}
        </div>

        {uploads.length === 0 ? (
          <p className='p-4 text-sm text-zinc-400'>No uploads yet.</p>
        ) : (
          <div className='overflow-x-auto'>
            <table className='w-full text-left text-sm'>
              <thead className='bg-zinc-900 text-xs uppercase tracking-wider text-zinc-400'>
                <tr>
                  <th className='border-b border-zinc-800 px-4 py-3'>File Name</th>
                  <th className='border-b border-zinc-800 px-4 py-3'>Timestamp</th>
                  <th className='border-b border-zinc-800 px-4 py-3'>Global Status</th>
                  <th className='border-b border-zinc-800 px-4 py-3'>Actions</th>
                </tr>
              </thead>
              <tbody>
                {uploads.map((event) => (
                  <tr key={event.id} className='border-b border-zinc-800/70'>
                    <td className='px-4 py-3 text-zinc-200'>{event.name}</td>
                    <td className='font-mono-data px-4 py-3 text-zinc-400'>{format(new Date(event.uploadedAt), 'PPpp')}</td>
                    <td className='px-4 py-3'>
                      <span className='rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-300'>
                        {event.status}
                      </span>
                    </td>
                    <td className='px-4 py-3'>
                      <Link
                        to={`/uploads/${event.rawfileId}`}
                        state={{ upload: event }}
                        className='inline-flex h-8 items-center justify-center rounded-md bg-cyan-400 px-3 text-xs font-semibold text-zinc-950 transition hover:bg-cyan-300'
                      >
                        View Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </section>
  )
}
