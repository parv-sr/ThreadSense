import { cn } from '@/lib/utils'
import React from 'react'

export const CardWithNoise = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      'relative overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950/50 backdrop-blur-xl',
      className
    )}
    {...props}
  >
    <div className='pointer-events-none absolute inset-0 opacity-[0.03]' style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.65%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E")' }} />
    <div className='relative z-10 h-full p-5'>{children}</div>
  </div>
))
CardWithNoise.displayName = 'CardWithNoise'
