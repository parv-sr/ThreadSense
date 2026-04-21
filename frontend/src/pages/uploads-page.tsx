import { useMemo, useState } from 'react'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { UploadDropzone } from '@/components/upload/upload-dropzone'
import { Card } from '@/components/ui/card'
import { useIngestMutation, useUploadsQuery } from '@/lib/api'
import type { IngestResponse } from '@/types/api'

export const UploadsPage = () => {
  const queryClient = useQueryClient()
  const ingestMutation = useIngestMutation()
  const { data: uploads = [] } = useUploadsQuery()
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)

  const handleUpload = async (file: File) => {
    try {
      setUploadProgress(0)
      const result = await ingestMutation.mutateAsync({
        file,
        onUploadProgress: (e) => {
          if (e.total) {
            setUploadProgress(Math.round((e.loaded * 100) / e.total))
          }
        },
      })
      setUploadProgress(null)
      const r = result as IngestResponse
      toast.success(r.status === 'ALREADY_EXISTS' ? 'Duplicate file detected.' : 'Upload queued successfully.')
      // Refresh upload list after a successful upload
      queryClient.invalidateQueries({ queryKey: ['uploads'] })
    } catch {
      toast.error('Upload failed. Please try again.')
    }
  }

  const totals = useMemo(
    () => ({
      total: uploads.length,
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

      {uploadProgress !== null ? (
        <div className='flex flex-col gap-2 rounded-xl border border-cyan-500/30 bg-cyan-900/10 px-4 py-4 text-cyan-200'>
          <div className="flex justify-between text-sm">
            <span>Uploading...</span>
            <span className="font-mono">{uploadProgress}%</span>
          </div>
          <div className='h-1 w-full overflow-hidden rounded bg-zinc-800'>
            <div className='h-full bg-cyan-400 transition-all duration-300' style={{ width: `${uploadProgress}%` }} />
          </div>
        </div>
      ) : (
        <UploadDropzone onFileSelect={handleUpload} />
      )}

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
                    <td className='font-mono-data px-4 py-3 text-zinc-400'>{format(new Date(event.uploaded_at), 'PPpp')}</td>
                    <td className='px-4 py-3'>
                      <span className='rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-300'>
                        {event.status}
                      </span>
                    </td>
                    <td className='px-4 py-3'>
                      <Link
                        to={`/uploads/${event.rawfile_id}`}
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
