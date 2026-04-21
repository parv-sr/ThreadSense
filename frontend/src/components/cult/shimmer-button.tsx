import React from 'react'
import { cn } from '@/lib/utils'

export const ShimmerButton = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement>>(
  ({ className, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'relative overflow-hidden rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-cyan-50 border border-zinc-800 transition-all hover:bg-zinc-800/90 hover:shadow-[0_0_20px_rgba(34,211,238,0.2)] disabled:opacity-50 disabled:pointer-events-none',
          className
        )}
        {...props}
      >
        <span className='absolute inset-0 z-0 overflow-hidden rounded-[inherit]'>
          <span className='absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-cyan-400/10 to-transparent' />
        </span>
        <span className='relative z-10 flex items-center justify-center gap-2'>
          {children}
        </span>
      </button>
    )
  }
)
ShimmerButton.displayName = 'ShimmerButton'
