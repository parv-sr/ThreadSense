import * as React from 'react'
import { cn } from '@/lib/utils'

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('glass-panel rounded-2xl text-slate-100 transition-all duration-200', className)}
      {...props}
    />
  ),
)
Card.displayName = 'Card'
