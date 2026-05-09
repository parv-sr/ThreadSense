import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

export const TypingAnimation = ({
  text,
  className,
  speed = 40,
}: {
  text: string
  className?: string
  speed?: number
}) => {
  const [displayedText, setDisplayedText] = useState('')

  useEffect(() => {
    let i = 0
    const interval = setInterval(() => {
      setDisplayedText(text.slice(0, i))
      i++
      if (i > text.length) clearInterval(interval)
    }, speed)
    return () => clearInterval(interval)
  }, [text, speed])

  return (
    <span className={cn('inline-block', className)}>
      {displayedText}
      <span className='ml-1 animate-pulse'>|</span>
    </span>
  )
}
