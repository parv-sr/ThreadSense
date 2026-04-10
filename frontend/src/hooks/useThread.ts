import { useMemo, useState } from 'react'

export const useThread = () => {
  const [threadId, setThreadId] = useState(() => crypto.randomUUID())

  const resetThread = () => setThreadId(crypto.randomUUID())

  return useMemo(() => ({ threadId, resetThread, setThreadId }), [threadId])
}
