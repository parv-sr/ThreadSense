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
  <div className='rounded-xl border border-slate-800 bg-slate-900 p-3'>
    <Textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder='Ask about listings, trends, or specific threads…' />
    <div className='mt-3 flex justify-end'>
      <Button onClick={onSubmit} disabled={loading || !value.trim()}>
        <SendHorizonal className='mr-2 h-4 w-4' />
        {loading ? 'Thinking...' : 'Send'}
      </Button>
    </div>
  </div>
)
