import ReactMarkdown from 'react-markdown'
import { Bot, User, FileText } from 'lucide-react'
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

export const MessageBubble = ({
  item,
  onSourceClick,
}: {
  item: ChatMessage
  onSourceClick: (sourceId: string) => void
}) => {
  if (item.type === 'user') {
    return (
      <div className='ml-auto flex max-w-2xl items-start gap-3'>
        <Card className='bg-emerald-700/20 p-4'>{item.message}</Card>
        <div className='rounded-full bg-emerald-600/20 p-2'><User className='h-4 w-4 text-emerald-400' /></div>
      </div>
    )
  }

  return (
    <div className='mr-auto flex max-w-4xl items-start gap-3'>
      <div className='rounded-full bg-indigo-600/20 p-2'><Bot className='h-4 w-4 text-indigo-300' /></div>
      <Card className='space-y-4 p-4'>
        <div className='overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-3' dangerouslySetInnerHTML={{ __html: item.tableHtml }} />
        <div>
          <p className='mb-2 text-xs uppercase text-slate-400'>Reasoning</p>
          <ReactMarkdown className='prose prose-invert max-w-none text-sm'>{item.reasoning}</ReactMarkdown>
        </div>
        <div className='flex flex-wrap items-center gap-2'>
          <Badge>Sources</Badge>
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
