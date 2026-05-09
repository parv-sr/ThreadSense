import React from 'react'
import { cn } from '@/lib/utils'

interface TextShimmerProps extends React.HTMLAttributes<HTMLHeadingElement> {
  children: React.ReactNode
  as?: React.ElementType
}

export function TextShimmer({
  children,
  as: Component = 'p',
  className,
  ...props
}: TextShimmerProps) {
  return (
    <Component
      className={cn(
        'animate-shimmer bg-[linear-gradient(110deg,#a1a1aa,45%,#e4e4e7,55%,#a1a1aa)] bg-[length:200%_100%] bg-clip-text text-transparent',
        className
      )}
      {...props}
    >
      {children}
    </Component>
  )
}
