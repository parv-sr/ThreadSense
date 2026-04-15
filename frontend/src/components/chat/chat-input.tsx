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
  <div className='glass-muted rounded-2xl p-3'>
    <Textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder='Ask about listings, trends, or specific threads…'
      onKeyDown={(e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault()
          onSubmit()
        }
      }}
      className='min-h-[92px] border-white/10 bg-slate-900/50'
    />
    <div className='mt-3 flex justify-end'>
      <Button onClick={onSubmit} disabled={loading || !value.trim()} className='transition hover:-translate-y-0.5'>
        <SendHorizonal className='mr-2 h-4 w-4' />
        {loading ? 'Thinking...' : 'Send'}
      </Button>
    </div>
  </div>
)
