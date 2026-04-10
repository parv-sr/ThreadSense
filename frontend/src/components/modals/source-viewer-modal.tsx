import { format } from 'date-fns'
import { Dialog } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import type { SourceChunk } from '@/lib/api'

export const SourceViewerModal = ({
  open,
  onOpenChange,
  source,
  loading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  source?: SourceChunk
  loading: boolean
}) => (
  <Dialog open={open} onOpenChange={onOpenChange} title='Source Message'>
    {loading ? (
      <div className='space-y-3'>
        <Skeleton className='h-5 w-1/2' />
        <Skeleton className='h-20 w-full' />
      </div>
    ) : source ? (
      <div className='space-y-3 text-sm'>
        <div className='text-slate-400'>
          <p>Sender: <span className='text-slate-100'>{source.sender}</span></p>
          <p>Timestamp: <span className='text-slate-100'>{format(new Date(source.created_at), 'PPpp')}</span></p>
        </div>
        <pre className='max-h-[50vh] overflow-auto rounded-lg bg-slate-950 p-4 text-slate-200'>{source.raw_text}</pre>
      </div>
    ) : (
      <p className='text-slate-400'>No source selected.</p>
    )}
  </Dialog>
)
