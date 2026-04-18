import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { Bot, User } from 'lucide-react'
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

interface ListingRow {
  config: string
  price: string
  location: string
  area: string
}

const parseListings = (tableHtml: string): ListingRow[] => {
  if (!tableHtml?.trim()) return []
  const parser = new DOMParser()
  const doc = parser.parseFromString(tableHtml, 'text/html')
  const rows = Array.from(doc.querySelectorAll('tbody tr'))
  const fallbackRows = rows.length > 0 ? rows : Array.from(doc.querySelectorAll('tr'))

  return fallbackRows
    .map((row) => Array.from(row.querySelectorAll('td')).map((td) => td.textContent?.trim() ?? '—'))
    .filter((cells) => cells.length > 0)
    .map((cells) => ({
      config: cells[0] ?? '—',
      price: cells[1] ?? '—',
      location: cells[2] ?? '—',
      area: cells[3] ?? '—',
    }))
}

export const MessageBubble = ({
  item,
  onSourceClick,
}: {
  item: ChatMessage
  onSourceClick: (sourceId: string) => void
}) => {
  const listings = useMemo(() => (item.type === 'assistant' ? parseListings(item.tableHtml) : []), [item])

  if (item.type === 'user') {
    return (
      <div className='ml-auto flex max-w-3xl items-start gap-3'>
        <Card className='border-zinc-800 bg-zinc-900 p-4 text-zinc-100'>{item.message}</Card>
        <div className='rounded-full border border-zinc-800 bg-zinc-900 p-2'>
          <User className='h-4 w-4 text-zinc-300' />
        </div>
      </div>
    )
  }

  return (
    <div className='mr-auto flex w-full max-w-6xl items-start gap-3'>
      <div className='rounded-full border border-zinc-800 bg-zinc-900 p-2'>
        <Bot className='h-4 w-4 text-cyan-300' />
      </div>
      <Card className='w-full space-y-4 border-zinc-800 bg-zinc-950 p-4'>
        <div className='overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950'>
          <table className='w-full border-collapse text-left text-sm'>
            <thead className='bg-zinc-900 text-xs uppercase tracking-wider text-zinc-400'>
              <tr>
                <th className='border-b border-zinc-800 px-3 py-3'>#</th>
                <th className='border-b border-zinc-800 px-3 py-3'>Configuration</th>
                <th className='border-b border-zinc-800 px-3 py-3'>Price</th>
                <th className='border-b border-zinc-800 px-3 py-3'>Location</th>
                <th className='border-b border-zinc-800 px-3 py-3'>Size/Area</th>
                <th className='border-b border-zinc-800 px-3 py-3'>Actions</th>
              </tr>
            </thead>
            <tbody>
              {listings.length === 0 ? (
                <tr>
                  <td className='px-3 py-4 text-zinc-500' colSpan={6}>
                    No tabular listing rows detected.
                  </td>
                </tr>
              ) : (
                listings.map((listing, index) => (
                  <tr key={`${item.id}-${index}`} className='border-b border-zinc-800/80'>
                    <td className='font-mono-data px-3 py-3 text-zinc-400'>{index + 1}</td>
                    <td className='px-3 py-3 text-zinc-100'>{listing.config}</td>
                    <td className='font-mono-data px-3 py-3 text-zinc-100'>{listing.price}</td>
                    <td className='px-3 py-3 text-zinc-300'>{listing.location}</td>
                    <td className='font-mono-data px-3 py-3 text-zinc-300'>{listing.area}</td>
                    <td className='px-3 py-3'>
                      <Button
                        size='sm'
                        className='h-7 rounded-md bg-cyan-400 px-2 text-[11px] font-semibold text-zinc-950 hover:bg-cyan-300'
                        onClick={() => onSourceClick(item.sources[index] ?? item.sources[0])}
                        disabled={item.sources.length === 0}
                      >
                        View Source
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div>
          <p className='mb-2 text-xs uppercase tracking-wide text-zinc-400'>Reasoning</p>
          <div className='prose prose-invert prose-p:leading-relaxed max-w-none text-sm text-zinc-300'>
            <ReactMarkdown>{item.reasoning}</ReactMarkdown>
          </div>
        </div>
      </Card>
    </div>
  )
}
