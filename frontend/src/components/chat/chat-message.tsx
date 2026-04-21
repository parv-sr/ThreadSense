import { useMemo, useCallback } from 'react'
import React, { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import { Bot, User, Copy, Check } from 'lucide-react'
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
  bhk: string
  price: string
  location: string
  contactNumber: string
  timestamp: string
  sender: string
  listingId: string
  chunkId: string
}

const parseListings = (tableHtml: string): ListingRow[] => {
  if (!tableHtml?.trim()) return []
  const parser = new DOMParser()
  const doc = parser.parseFromString(tableHtml, 'text/html')
  return Array.from(doc.querySelectorAll('tbody tr'))
    .map((row) => {
      const cells = Array.from(row.querySelectorAll('td')).map((td) => td.textContent?.trim() ?? '—')
      return {
        bhk: cells[0] ?? '—',
        price: cells[1] ?? '—',
        location: cells[2] ?? '—',
        contactNumber: cells[3] ?? '—',
        timestamp: cells[4] ?? '—',
        sender: cells[5] ?? '—',
        listingId: cells[6] ?? '—',
        chunkId: row.querySelector('button[data-chunk-id]')?.getAttribute('data-chunk-id') ?? '',
      }
    })
    .filter(row => row.bhk !== '—' || row.price !== '—')
}

const CopyButton = memo(({ text }: { text: string }) => {
  const [copied, setCopied] = React.useState(false)

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [text])

  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-6 w-6 rounded text-zinc-400 hover:text-cyan-300 hover:bg-zinc-800"
      onClick={handleCopy}
      aria-label="Copy row data"
    >
      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
    </Button>
  )
})

export const MessageBubble = memo(({
  item,
  onSourceClick,
}: {
  item: ChatMessage
  onSourceClick: (sourceId: string) => void
}) => {
  const listings = useMemo(() => (item.type === 'assistant' ? parseListings(item.tableHtml) : []), [item])

  if (item.type === 'user') {
    return (
      <div className='ml-auto flex max-w-3xl items-start gap-3 animate-in slide-in-from-right-4 duration-300'>
        <Card className='border-zinc-800 bg-zinc-900 p-4 text-zinc-100 shadow-md'>{item.message}</Card>
        <div className='rounded-full border border-zinc-800 bg-zinc-900 p-2 shadow-inner'>
          <User className='h-4 w-4 text-zinc-300' />
        </div>
      </div>
    )
  }

  return (
    <div className='mr-auto flex w-full max-w-6xl items-start gap-3 animate-in slide-in-from-left-4 fade-in duration-500'>
      <div className='rounded-full border border-zinc-800 bg-zinc-900 p-2 shadow-inner'>
        <Bot className='h-4 w-4 text-cyan-400' />
      </div>
      <Card className='w-full space-y-4 border-zinc-800/60 bg-zinc-950/80 backdrop-blur-md p-5 shadow-xl'>
        {listings.length > 0 && (
          <div className='overflow-x-auto rounded-xl border border-zinc-800/80 bg-zinc-950/90 shadow-inner max-h-[400px]'>
            <table className='w-full border-collapse text-left text-sm relative'>
              <thead className='bg-zinc-900/90 backdrop-blur text-xs uppercase tracking-wider text-zinc-400 sticky top-0 z-10 shadow-sm'>
                <tr>
                  <th scope="col" className='border-b border-zinc-800 px-3 py-3 font-semibold'>BHK</th>
                  <th scope="col" className='border-b border-zinc-800 px-3 py-3 font-semibold'>Price</th>
                  <th scope="col" className='border-b border-zinc-800 px-3 py-3 font-semibold'>Location</th>
                  <th scope="col" className='border-b border-zinc-800 px-3 py-3 font-semibold'>Contact</th>
                  <th scope="col" className='border-b border-zinc-800 px-3 py-3 font-semibold'>Timestamp</th>
                  <th scope="col" className='border-b border-zinc-800 px-3 py-3 font-semibold'>Sender</th>
                  <th scope="col" className='border-b border-zinc-800 px-3 py-3 font-semibold'>ID</th>
                  <th scope="col" className='border-b border-zinc-800 px-3 py-3 font-semibold'>Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {listings.map((listing, index) => (
                  <tr key={`${item.id}-${index}`} className='hover:bg-zinc-800/40 transition-colors group'>
                    <td className='px-3 py-3 text-zinc-100 font-medium'>{listing.bhk}</td>
                    <td className='font-mono-data px-3 py-3 text-cyan-100'>{listing.price}</td>
                    <td className='px-3 py-3 text-zinc-300'>{listing.location}</td>
                    <td className='font-mono-data px-3 py-3 text-zinc-400'>{listing.contactNumber}</td>
                    <td className='font-mono-data px-3 py-3 text-zinc-500 text-xs'>{listing.timestamp}</td>
                    <td className='px-3 py-3 text-zinc-400 text-xs'>{listing.sender}</td>
                    <td className='font-mono-data px-3 py-3 text-zinc-500 text-xs max-w-[80px] truncate' title={listing.listingId}>
                      {listing.listingId}
                    </td>
                    <td className='px-3 py-3 flex items-center gap-2'>
                      <CopyButton 
                        text={`BHK: ${listing.bhk}\nPrice: ${listing.price}\nLoc: ${listing.location}\nContact: ${listing.contactNumber}`} 
                      />
                      <Button
                        size='sm'
                        className='h-7 rounded bg-cyan-500/20 px-2 text-[11px] font-semibold text-cyan-300 hover:bg-cyan-500/30 hover:text-cyan-100 border border-cyan-500/30 transition-colors'
                        onClick={() => onSourceClick(listing.chunkId || item.sources[index] || item.sources[0])}
                        disabled={!listing.chunkId && item.sources.length === 0}
                      >
                        Source
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div>
          {listings.length > 0 && <p className='mb-2 text-xs uppercase tracking-wide text-zinc-500 font-semibold'>Reasoning</p>}
          <div className='prose prose-invert prose-p:leading-relaxed max-w-none text-sm text-zinc-300 prose-a:text-cyan-400 hover:prose-a:text-cyan-300 prose-strong:text-zinc-100'>
            <ReactMarkdown>{item.reasoning}</ReactMarkdown>
          </div>
        </div>
      </Card>
    </div>
  )
})
MessageBubble.displayName = 'MessageBubble'
