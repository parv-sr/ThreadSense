import React, { memo, useCallback, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { Bot, Check, Copy, User } from 'lucide-react'
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
  id: string
  transaction: string
  property: string
  location: string
  bhk: string
  price: string
}

const parseListings = (tableHtml: string): ListingRow[] => {
  if (!tableHtml?.trim()) return []
  const parser = new DOMParser()
  const doc = parser.parseFromString(tableHtml, 'text/html')
  return Array.from(doc.querySelectorAll('tbody tr'))
    .map((row) => {
      const cells = Array.from(row.querySelectorAll('td')).map((td) => td.textContent?.trim() ?? '-')
      return {
        id: row.querySelector('button[data-listing-id]')?.getAttribute('data-listing-id') ?? cells[0] ?? '',
        transaction: cells[1] ?? '-',
        property: cells[2] ?? '-',
        location: cells[3] ?? '-',
        bhk: cells[4] ?? '-',
        price: cells[5] ?? '-',
      }
    })
    .filter((row) => row.id)
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
      variant='ghost'
      size='icon'
      className='h-7 w-7 rounded-md text-zinc-400 hover:bg-zinc-800 hover:text-cyan-300'
      onClick={handleCopy}
      aria-label='Copy row data'
    >
      {copied ? <Check className='h-3.5 w-3.5' /> : <Copy className='h-3.5 w-3.5' />}
    </Button>
  )
})

export const MessageBubble = memo(
  ({
    item,
    onSourceClick,
  }: {
    item: ChatMessage
    onSourceClick: (listingId: string) => void
  }) => {
    const listings = useMemo(() => (item.type === 'assistant' ? parseListings(item.tableHtml) : []), [item])

    if (item.type === 'user') {
      return (
        <div className='ml-auto flex max-w-3xl items-start gap-3'>
          <Card className='rounded-md border-zinc-800 bg-zinc-900 p-4 text-zinc-100'>{item.message}</Card>
          <div className='rounded-md border border-zinc-800 bg-zinc-900 p-2'>
            <User className='h-4 w-4 text-zinc-300' />
          </div>
        </div>
      )
    }

    return (
      <div className='mr-auto flex w-full max-w-6xl items-start gap-3'>
        <div className='rounded-md border border-zinc-800 bg-zinc-900 p-2'>
          <Bot className='h-4 w-4 text-cyan-400' />
        </div>
        <Card className='w-full space-y-4 rounded-md border-zinc-800 bg-zinc-950 p-5'>
          {listings.length > 0 && (
            <div className='max-h-[420px] overflow-x-auto border border-zinc-800 bg-zinc-950'>
              <table className='w-full border-collapse text-left text-sm'>
                <thead className='sticky top-0 bg-zinc-900 text-xs uppercase text-zinc-400'>
                  <tr>
                    <th className='border-b border-zinc-800 px-3 py-3 font-semibold'>ID</th>
                    <th className='border-b border-zinc-800 px-3 py-3 font-semibold'>Transaction</th>
                    <th className='border-b border-zinc-800 px-3 py-3 font-semibold'>Property</th>
                    <th className='border-b border-zinc-800 px-3 py-3 font-semibold'>Location</th>
                    <th className='border-b border-zinc-800 px-3 py-3 font-semibold'>BHK</th>
                    <th className='border-b border-zinc-800 px-3 py-3 font-semibold'>Price</th>
                    <th className='border-b border-zinc-800 px-3 py-3 font-semibold'>Actions</th>
                  </tr>
                </thead>
                <tbody className='divide-y divide-zinc-800'>
                  {listings.map((listing) => (
                    <tr key={`${item.id}-${listing.id}`} className='hover:bg-zinc-900/70'>
                      <td className='font-mono-data max-w-[150px] truncate px-3 py-3 text-xs text-cyan-200'>
                        <button className='hover:underline' onClick={() => onSourceClick(listing.id)}>
                          {listing.id}
                        </button>
                      </td>
                      <td className='px-3 py-3 text-zinc-300'>{listing.transaction}</td>
                      <td className='px-3 py-3 text-zinc-300'>{listing.property}</td>
                      <td className='px-3 py-3 text-zinc-300'>{listing.location}</td>
                      <td className='px-3 py-3 font-medium text-zinc-100'>{listing.bhk}</td>
                      <td className='font-mono-data px-3 py-3 text-cyan-100'>{listing.price}</td>
                      <td className='flex items-center gap-2 px-3 py-3'>
                        <CopyButton
                          text={`ID: ${listing.id}\nTransaction: ${listing.transaction}\nProperty: ${listing.property}\nLocation: ${listing.location}\nBHK: ${listing.bhk}\nPrice: ${listing.price}`}
                        />
                        <Button
                          size='sm'
                          variant='outline'
                          className='h-7 rounded-md px-2 text-[11px]'
                          onClick={() => onSourceClick(listing.id)}
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
            {listings.length > 0 && <p className='mb-2 text-xs uppercase text-zinc-500'>Reasoning</p>}
            <div className='prose prose-invert max-w-none text-sm text-zinc-300 prose-a:text-cyan-400 prose-strong:text-zinc-100'>
              <ReactMarkdown>{item.reasoning}</ReactMarkdown>
            </div>
          </div>
        </Card>
      </div>
    )
  },
)

MessageBubble.displayName = 'MessageBubble'
