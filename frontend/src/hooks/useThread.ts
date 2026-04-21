import { useCallback, useState } from 'react'

export const useThread = () => {
  const [threadId, setThreadId] = useState(() => crypto.randomUUID())
  const resetThread = useCallback(() => setThreadId(crypto.randomUUID()), [])
  return { threadId, resetThread }
}
