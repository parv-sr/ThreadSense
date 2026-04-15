import * as React from 'react'
import { cn } from '@/lib/utils'

export const Badge = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <span className={cn('rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300', className)}>
    {children}
  </span>
)
