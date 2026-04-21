import { format } from 'date-fns'
import { AlertTriangle } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import type { SourceChunk } from '@/types/api'

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
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className='sm:max-w-xl'>
      <DialogHeader>
        <DialogTitle>Source Message</DialogTitle>
      </DialogHeader>
      <div className='mt-4'>
        {loading ? (
          <div className='space-y-3'>
            <Skeleton className='h-5 w-1/2 bg-zinc-800' />
            <Skeleton className='h-20 w-full bg-zinc-800' />
          </div>
        ) : error ? (
          <div className='flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200'>
            <AlertTriangle className='mt-0.5 h-4 w-4 shrink-0' />
            <p>{error}</p>
          </div>
        ) : source ? (
          <div className='space-y-3 text-sm'>
            <div className='w-full rounded-2xl rounded-bl-sm border border-emerald-700/70 bg-emerald-600/90 p-4 text-emerald-50 shadow-md'>
              <p className='mb-2 text-xs uppercase tracking-wider text-emerald-100/90'>WhatsApp Source Bubble</p>
              <pre className='font-mono-data max-h-[42vh] overflow-auto whitespace-pre-wrap text-[13px] leading-relaxed'>
                {source.raw_text}
              </pre>
              <div className='mt-3 border-t border-emerald-500/50 pt-2 text-xs text-emerald-100/95'>
                <p>
                  Sender: <span className='font-semibold'>{source.sender ?? 'Unknown'}</span>
                </p>
                <p>
                  Timestamp:{' '}
                  <span className='font-semibold'>
                    {source.created_at ? format(new Date(source.created_at), 'PPpp') : 'Unavailable'}
                  </span>
                </p>
              </div>
            </div>
          </div>
        ) : (
          <p className='text-zinc-400'>No source selected.</p>
        )}
      </div>
    </DialogContent>
  </Dialog>
)
