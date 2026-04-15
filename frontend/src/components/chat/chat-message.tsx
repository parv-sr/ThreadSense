import ReactMarkdown from 'react-markdown'
import { Bot, FileText, User } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

export interface AssistantMessage {
  id: string
  type: 'assistant'
  tableHtml: string
  reasoning: string
  sources: string[]
}

export interface UserMessage {
  id: string
  type: 'user'
  message: string
}

export type ChatMessage = AssistantMessage | UserMessage

const sanitizeTableHtml = (tableHtml: string) =>
  tableHtml
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '')
    .replace(/on\w+="[^"]*"/g, '')
    .replace(/on\w+='[^']*'/g, '')

export const MessageBubble = ({
  item,
  onSourceClick,
}: {
  item: ChatMessage
  onSourceClick: (sourceId: string) => void
}) => {
  if (item.type === 'user') {
    return (
      <div className='ml-auto flex max-w-2xl animate-in slide-in-from-bottom-1 duration-300 items-start gap-3'>
        <Card className='border-cyan-400/20 bg-cyan-500/10 p-4'>{item.message}</Card>
        <div className='rounded-full border border-cyan-300/25 bg-cyan-400/10 p-2'>
          <User className='h-4 w-4 text-cyan-200' />
        </div>
      </div>
    )
  }

  return (
    <div className='mr-auto flex max-w-4xl animate-in slide-in-from-bottom-1 duration-300 items-start gap-3'>
      <div className='rounded-full border border-indigo-300/30 bg-indigo-400/10 p-2'>
        <Bot className='h-4 w-4 text-indigo-200' />
      </div>
      <Card className='space-y-4 p-4'>
        <div
          className='overflow-x-auto rounded-xl border border-white/10 bg-slate-950/70 p-3'
          dangerouslySetInnerHTML={{ __html: sanitizeTableHtml(item.tableHtml) }}
        />
        <div>
          <p className='mb-2 text-xs uppercase tracking-wide text-slate-400'>Reasoning</p>
          <div className='prose prose-invert prose-p:leading-relaxed max-w-none text-sm'>
            <ReactMarkdown>{item.reasoning}</ReactMarkdown>
          </div>
        </div>
        <div className='flex flex-wrap items-center gap-2'>
          <Badge className='bg-white/10 text-slate-200'>Sources</Badge>
          {item.sources.length === 0 ? (
            <span className='text-xs text-slate-400'>No sources returned.</span>
          ) : (
            item.sources.map((source) => (
              <Button key={source} variant='outline' size='sm' onClick={() => onSourceClick(source)}>
                <FileText className='mr-2 h-3 w-3' /> View Source
              </Button>
            ))
          )}
        </div>
      </Card>
    </div>
  )
}
