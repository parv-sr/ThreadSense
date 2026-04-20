import * as React from 'react'
import { cn } from '@/lib/utils'

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('tactile-panel rounded-2xl text-zinc-100', className)} {...props} />
  ),
)
Card.displayName = 'Card'
