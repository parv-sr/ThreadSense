import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

export const AnimatedNumber = ({ value, className }: { value: number; className?: string }) => {
  const [displayValue, setDisplayValue] = useState(value)

  useEffect(() => {
    let start = displayValue
    const end = value
    if (start === end) return

    const duration = 1000
    const startTime = performance.now()

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime
      const progress = Math.min(elapsed / duration, 1)
      const current = Math.floor(start + (end - start) * progress)
      
      setDisplayValue(current)

      if (progress < 1) {
        requestAnimationFrame(animate)
      } else {
        setDisplayValue(end)
      }
    }

    requestAnimationFrame(animate)
  }, [value])

  return <span className={cn('font-mono tabular-nums', className)}>{displayValue.toLocaleString()}</span>
}
