import * as React from 'react'
import { cn } from '@/lib/utils'
import { ShimmerButton } from '@/components/cult/shimmer-button'

type ButtonVariant = 'default' | 'destructive' | 'outline' | 'ghost' | 'secondary'
type ButtonSize = 'default' | 'sm' | 'lg' | 'icon'

const variantClasses: Record<ButtonVariant, string> = {
  default: 'bg-cyan-400 text-zinc-950 hover:bg-cyan-300',
  destructive: 'bg-red-500 text-white hover:bg-red-400',
  outline: 'border border-zinc-700 bg-zinc-900 text-zinc-100 hover:bg-zinc-800',
  ghost: 'bg-transparent text-zinc-200 hover:bg-zinc-800',
  secondary: 'border border-zinc-700 bg-zinc-800 text-zinc-100 hover:bg-zinc-700',
}

const sizeClasses: Record<ButtonSize, string> = {
  default: 'h-10 px-4 py-2',
  sm: 'h-8 rounded-md px-3 text-xs',
  lg: 'h-11 rounded-md px-8',
  icon: 'h-9 w-9',
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    if (variant === 'default') {
      return (
        <ShimmerButton
          ref={ref}
          className={cn(sizeClasses[size], className)}
          {...props}
        />
      )
    }

    return (
      <button
        ref={ref}
        className={cn(
          'inline-flex items-center justify-center whitespace-nowrap rounded-xl text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70 disabled:pointer-events-none disabled:opacity-50',
          variantClasses[variant],
          sizeClasses[size],
          className,
        )}
        {...props}
      />
    )
  },
)
Button.displayName = 'Button'
