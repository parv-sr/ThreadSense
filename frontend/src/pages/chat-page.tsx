import { useState } from 'react'
import { PlusCircle } from 'lucide-react'
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
    if (!input.trim()) return

    const userMsg: ChatMessage = { id: crypto.randomUUID(), type: 'user', message: input }
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
    <section className='flex h-[calc(100vh-120px)] flex-col gap-4'>
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='text-2xl font-semibold'>Chat Workspace</h1>
          <p className='text-sm text-slate-400'>Thread: {threadId}</p>
        </div>
        <Button variant='secondary' onClick={() => { resetThread(); setMessages([]); toast.success('Started a new thread.') }}>
          <PlusCircle className='mr-2 h-4 w-4' /> New Thread
        </Button>
      </div>

      <Card className='flex-1 overflow-hidden p-0'>
        <div ref={scrollRef} className='h-full space-y-4 overflow-y-auto p-4'>
          {messages.length === 0 ? (
            <div className='grid h-full place-items-center text-center text-slate-400'>
              <div>
                <p className='mb-2 text-lg text-slate-200'>Welcome to ThreadSense v2</p>
                <p>Ask your first question to generate structured insights from your WhatsApp thread data.</p>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                item={msg}
                onSourceClick={(sourceId) => {
                  setActiveSourceId(sourceId)
                  setOpenSource(true)
                }}
              />
            ))
          )}
        </div>
      </Card>

      <ChatInput value={input} onChange={setInput} onSubmit={sendMessage} loading={chatMutation.isPending} />

      <SourceViewerModal open={openSource} onOpenChange={setOpenSource} source={sourceQuery.data} loading={sourceQuery.isLoading} />
    </section>
  )
}
