import * as React from 'react'
import { cn } from '@/lib/utils'

type ButtonVariant = 'default' | 'destructive' | 'outline' | 'ghost' | 'secondary'
type ButtonSize = 'default' | 'sm' | 'lg' | 'icon'

const variantClasses: Record<ButtonVariant, string> = {
  default:
    'bg-gradient-to-r from-indigo-500/95 to-cyan-400/95 text-white shadow-lg shadow-cyan-500/20 hover:from-indigo-400 hover:to-cyan-300',
  destructive: 'bg-red-500/90 text-white shadow-sm hover:bg-red-400',
  outline: 'border border-white/20 bg-white/5 hover:bg-white/10',
  ghost: 'bg-transparent hover:bg-white/10',
  secondary: 'border border-white/15 bg-slate-700/60 text-slate-100 hover:bg-slate-600/70',
}

const sizeClasses: Record<ButtonSize, string> = {
  default: 'h-10 px-4 py-2',
  sm: 'h-8 rounded-md px-3 text-xs',
  lg: 'h-11 rounded-md px-8',
  icon: 'h-9 w-9',
}

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 disabled:pointer-events-none disabled:opacity-50',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    />
  ),
)
Button.displayName = 'Button'
