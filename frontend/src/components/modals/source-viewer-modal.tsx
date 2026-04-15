import { format } from 'date-fns'
import { AlertTriangle } from 'lucide-react'
import { Dialog } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import type { SourceChunk } from '@/lib/api'

export const SourceViewerModal = ({
  open,
  onOpenChange,
  source,
  loading,
  error,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  source?: SourceChunk
  loading: boolean
  error?: string
}) => (
  <Dialog open={open} onOpenChange={onOpenChange} title='Source Message'>
    {loading ? (
      <div className='space-y-3'>
        <Skeleton className='h-5 w-1/2' />
        <Skeleton className='h-20 w-full' />
      </div>
    ) : error ? (
      <div className='flex items-start gap-2 rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-200'>
        <AlertTriangle className='mt-0.5 h-4 w-4 shrink-0' />
        <p>{error}</p>
      </div>
    ) : source ? (
      <div className='space-y-3 text-sm'>
        <div className='text-slate-300'>
          <p>
            Sender: <span className='text-slate-100'>{source.sender}</span>
          </p>
          <p>
            Timestamp: <span className='text-slate-100'>{format(new Date(source.created_at), 'PPpp')}</span>
          </p>
        </div>
        <pre className='glass-muted max-h-[50vh] overflow-auto rounded-xl p-4 text-slate-200'>{source.raw_text}</pre>
      </div>
    ) : (
      <p className='text-slate-400'>No source selected.</p>
    )}
  </Dialog>
)
