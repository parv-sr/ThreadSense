import { SendHorizonal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

export const ChatInput = ({
  value,
  onChange,
  onSubmit,
  loading,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  loading: boolean
}) => (
  <div className='sticky bottom-0 z-10 rounded-2xl border border-zinc-700 bg-zinc-900 p-4 shadow-[0_-10px_30px_rgba(0,0,0,0.45)]'>
    <Textarea
      maxLength={6000}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder='> query listings by price, area, and location...'
      onKeyDown={(e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault()
          onSubmit()
        }
      }}
      className='font-mono-data min-h-[140px] border-zinc-700 bg-zinc-950 text-zinc-100'
    />
    <div className='mt-3 flex justify-between items-center'>
      <span className="text-xs text-zinc-500 font-mono">{value.length}/6000</span>
      <Button onClick={onSubmit} disabled={loading || !value.trim()}>
        <SendHorizonal className='mr-2 h-4 w-4' />
        {loading ? 'Running...' : 'Execute'}
      </Button>
    </div>
  </div>
)
