import { useEffect, useState, useRef } from 'react'
import { supabase } from '../lib/supabase'
import { env } from '../lib/env'

interface UploadStreamState {
  snapshot: any | null
  heartbeat: string | null
  isDone: boolean
  isConnected: boolean
  error: string | null
}

export const useUploadStream = (rawfileId: string | undefined) => {
  const [state, setState] = useState<UploadStreamState>({
    snapshot: null,
    heartbeat: null,
    isDone: false,
    isConnected: false,
    error: null,
  })
  
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!rawfileId) return

    let isMounted = true
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    const connectStream = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        const token = session?.access_token

        if (!token) {
          if (isMounted) setState(s => ({ ...s, error: 'No active session' }))
          return
        }

        const url = `${env.apiUrl}/ingest/uploads/${rawfileId}/stream`

        const response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'text/event-stream',
          },
          signal: abortController.signal,
        })

        if (!response.ok) {
          throw new Error(`Connection failed: ${response.statusText}`)
        }

        if (isMounted) setState(s => ({ ...s, isConnected: true, error: null }))

        const reader = response.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const chunks = buffer.split('\n\n')
          
          buffer = chunks.pop() || '' // Keep the last incomplete chunk

          for (const chunk of chunks) {
            const lines = chunk.split('\n')
            let eventType = 'message'
            let eventData = ''

            for (const line of lines) {
              if (line.startsWith('event:')) {
                eventType = line.slice(6).trim()
              } else if (line.startsWith('data:')) {
                eventData += line.slice(5).trim()
              }
            }

            if (eventData) {
              if (eventType === 'snapshot') {
                try {
                  const parsed = JSON.parse(eventData)
                  if (isMounted) setState(s => ({ ...s, snapshot: parsed }))
                } catch (e) {
                  console.error('Failed to parse snapshot', e)
                }
              } else if (eventType === 'heartbeat') {
                if (isMounted) setState(s => ({ ...s, heartbeat: eventData }))
              } else if (eventType === 'done') {
                if (isMounted) setState(s => ({ ...s, isDone: true, isConnected: false }))
                abortController.abort() // Close the connection
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name !== 'AbortError' && isMounted) {
          setState(s => ({ ...s, error: err.message, isConnected: false }))
        }
      }
    }

    connectStream()

    return () => {
      isMounted = false
      abortController.abort()
    }
  }, [rawfileId])

  return state
}
