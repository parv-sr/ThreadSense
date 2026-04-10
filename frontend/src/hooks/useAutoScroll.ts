import { useEffect, useRef } from 'react'

export const useAutoScroll = <T,>(dependency: T) => {
  const ref = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!ref.current) return
    ref.current.scrollTo({ top: ref.current.scrollHeight, behavior: 'smooth' })
  }, [dependency])

  return ref
}
