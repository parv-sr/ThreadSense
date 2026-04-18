import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Clock3, Files, Loader2 } from 'lucide-react'
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
      total: uploads.length,
      uploaded: uploads.filter((upload) => upload.status !== 'ALREADY_EXISTS').length,
      duplicates: uploads.filter((upload) => upload.status === 'ALREADY_EXISTS').length,
    }),
    [uploads],
  )

  return (
    <section className='space-y-6'>
      <div className='flex items-end justify-between'>
        <div>
          <h1 className='text-2xl font-semibold tracking-tight'>Upload Operations</h1>
          <p className='text-sm text-zinc-400'>Track ingest queue, dedupe progression, and drill into per-file diagnostics.</p>
        </div>
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
          <p className='text-xs uppercase tracking-wide text-zinc-400'>Unique Uploads</p>
          <p className='font-mono-data mt-2 text-3xl font-bold'>{totals.uploaded}</p>
        </Card>
        <Card className='p-4'>
          <p className='text-xs uppercase tracking-wide text-zinc-400'>Duplicates</p>
          <p className='font-mono-data mt-2 text-3xl font-bold'>{totals.duplicates}</p>
        </Card>
      </div>

      <Card className='overflow-hidden p-0'>
        <div className='flex items-center justify-between border-b border-zinc-800 bg-zinc-900/50 px-4 py-3'>
          <div>
            <h2 className='text-lg font-semibold'>Uploads List</h2>
            <p className='text-xs text-zinc-500'>File Name · Timestamp · Global Status · Actions</p>
          </div>
          {ingestMutation.isPending ? <Loader2 className='h-4 w-4 animate-spin text-cyan-300' /> : null}
        </div>

        {uploads.length === 0 ? (
          <div className='flex flex-col items-center justify-center gap-2 p-10 text-zinc-500'>
            <Files className='h-6 w-6' />
            <p className='text-sm'>No uploads yet.</p>
          </div>
        ) : (
          <div className='overflow-x-auto'>
            <table className='w-full min-w-[920px] text-left text-sm'>
              <thead className='bg-zinc-900 text-xs uppercase tracking-wider text-zinc-400'>
                <tr>
                  <th className='border-b border-zinc-800 px-4 py-3'>File Name</th>
                  <th className='border-b border-zinc-800 px-4 py-3'>Timestamp</th>
                  <th className='border-b border-zinc-800 px-4 py-3'>Global Status</th>
                  <th className='border-b border-zinc-800 px-4 py-3'>Size</th>
                  <th className='border-b border-zinc-800 px-4 py-3 text-right'>Actions</th>
                </tr>
              </thead>
              <tbody>
                {uploads.map((upload) => (
                  <tr key={upload.id} className='border-b border-zinc-800/70 hover:bg-zinc-900/40'>
                    <td className='px-4 py-3 text-zinc-200'>{upload.name}</td>
                    <td className='px-4 py-3 text-zinc-400'>
                      <div className='font-mono-data flex items-center gap-2'>
                        <Clock3 className='h-3.5 w-3.5' />
                        {format(new Date(upload.uploadedAt), 'PPpp')}
                      </div>
                    </td>
                    <td className='px-4 py-3'>
                      <span className='rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-300'>
                        {upload.status}
                      </span>
                    </td>
                    <td className='px-4 py-3 font-mono-data text-zinc-400'>{upload.fileSize.toLocaleString()} B</td>
                    <td className='px-4 py-3 text-right'>
                      <Link
                        to={`/uploads/${upload.rawfileId}`}
                        state={{ upload }}
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
