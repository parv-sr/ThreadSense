import { useEffect, useState, useRef } from 'react'
import { supabase } from '../lib/supabase'
import { env } from '../lib/env'
import type { UploadDetail } from '../types/api'

interface UploadStreamState {
  snapshot: UploadDetail | null
  heartbeat: string | null
  isDone: boolean
  isConnected: boolean
  error: string | null
}

const MAX_RETRIES = 5

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
      // Fetch token inside connectStream so each retry gets a fresh token
      let token: string | undefined
      for (let tokenAttempt = 0; tokenAttempt < 5; tokenAttempt++) {
        const { data: { session } } = await supabase.auth.getSession()
        token = session?.access_token
        if (token) break
        await new Promise(resolve => setTimeout(resolve, 500 * (tokenAttempt + 1)))
      }

      if (!token) {
        if (isMounted) setState(s => ({ ...s, error: 'Authentication required. Please log in.' }))
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
                const parsed = JSON.parse(eventData) as UploadDetail
                if (isMounted) setState(s => ({ ...s, snapshot: parsed }))
              } catch (e) {
                console.error('Failed to parse snapshot', e)
              }
            } else if (eventType === 'heartbeat') {
              if (isMounted) setState(s => ({ ...s, heartbeat: eventData }))
            } else if (eventType === 'done') {
              if (isMounted) setState(s => ({ ...s, isDone: true, isConnected: false }))
              return // clean exit — don't abort here, let the reader finish
            }
          }
        }
      }
    }

    // Retry wrapper with exponential backoff
    const connectWithRetry = async () => {
      let attempt = 0
      while (attempt < MAX_RETRIES && isMounted) {
        try {
          await connectStream()
          break // clean exit (done event received or stream ended normally)
        } catch (err: any) {
          if (!isMounted) break
          if (err.name === 'AbortError') break
          attempt++
          if (attempt >= MAX_RETRIES) {
            setState(s => ({
              ...s,
              error: `Stream failed after ${MAX_RETRIES} attempts: ${err.message}`,
              isConnected: false,
            }))
            break
          }
          const delay = Math.min(1000 * 2 ** attempt, 30000)
          console.warn(`[useUploadStream] Retry ${attempt}/${MAX_RETRIES} in ${delay}ms:`, err.message)
          if (isMounted) setState(s => ({ ...s, isConnected: false, error: null }))
          await new Promise(r => setTimeout(r, delay))
        }
      }
    }

    connectWithRetry()

    return () => {
      isMounted = false
      abortController.abort()
    }
  }, [rawfileId])

  return state
}
