import { useState } from 'react'
import { AlertTriangle, Loader2, PlusCircle } from 'lucide-react'
import { toast } from 'sonner'
import { ChatInput } from '@/components/chat/chat-input'
import { type ChatMessage, MessageBubble } from '@/components/chat/chat-message'
import { SourceViewerModal } from '@/components/modals/source-viewer-modal'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useAutoScroll } from '@/hooks/useAutoScroll'
import { useThread } from '@/hooks/useThread'
import { useChatMutation, useSourceQuery } from '@/lib/api'

export const ChatPage = () => {
  const { threadId, resetThread } = useThread()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [openSource, setOpenSource] = useState(false)
  const [activeSourceId, setActiveSourceId] = useState<string>()

  const chatMutation = useChatMutation()
  const sourceQuery = useSourceQuery(activeSourceId, openSource)
  const scrollRef = useAutoScroll(messages)

  const sendMessage = async () => {
    const trimmed = input.trim()
    if (!trimmed) return

    const userMsg: ChatMessage = { id: crypto.randomUUID(), type: 'user', message: trimmed }
    setMessages((prev) => [...prev, userMsg])
    setInput('')

    try {
      const data = await chatMutation.mutateAsync({ message: userMsg.message, thread_id: threadId })
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          type: 'assistant',
          tableHtml: data.table_html,
          reasoning: data.reasoning,
          sources: data.sources,
        },
      ])
    } catch {
      toast.error('Could not get response from backend.')
    }
  }

  return (
    <section className='flex h-[calc(100vh-160px)] min-h-[620px] flex-col gap-4'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-semibold tracking-tight'>Chat Workspace</h1>
          <p className='font-mono-data text-sm text-zinc-400'>Thread ID: {threadId}</p>
        </div>
        <Button
          variant='outline'
          onClick={() => {
            resetThread()
            setMessages([])
            toast.success('Started a new conversation.')
          }}
        >
          <PlusCircle className='mr-2 h-4 w-4' /> New Conversation
        </Button>
      </div>

      <Card className='flex-1 overflow-hidden border-zinc-800 bg-zinc-950 p-0'>
        <div ref={scrollRef} className='h-full space-y-4 overflow-y-auto p-4'>
          {messages.length === 0 ? (
            <div className='grid h-full place-items-center text-center text-zinc-400'>
              <div className='max-w-lg'>
                <p className='mb-2 text-lg text-zinc-100'>Welcome to ThreadSense</p>
                <p>Ask your first question to generate structured insights from WhatsApp thread data.</p>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                item={msg}
                onSourceClick={(sourceId) => {
                  if (!sourceId) return
                  setActiveSourceId(sourceId)
                  setOpenSource(true)
                }}
              />
            ))
          )}

          {chatMutation.isPending ? (
            <div className='mr-auto flex max-w-md items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-300'>
              <Loader2 className='h-4 w-4 animate-spin text-cyan-300' /> Thinking through your request...
            </div>
          ) : null}

          {chatMutation.isError ? (
            <div className='mr-auto flex max-w-md items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200'>
              <AlertTriangle className='h-4 w-4' /> Cannot connect to backend. Is the backend server running on port
              8000?
            </div>
          ) : null}
        </div>
      </Card>

        <ChatInput value={input} onChange={setInput} onSubmit={sendMessage} loading={chatMutation.isPending} />
      </div>

      <SourceViewerModal
        open={openSource}
        onOpenChange={setOpenSource}
        source={sourceQuery.data}
        loading={sourceQuery.isLoading}
        error={sourceQuery.isError ? 'Could not load source from /chat/source/{chunk_id}.' : undefined}
      />
    </section>
  )
}
