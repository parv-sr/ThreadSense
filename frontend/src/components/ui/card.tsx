import * as React from 'react'
import { CardWithNoise } from '@/components/cult/card-with-noise'

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <CardWithNoise ref={ref} className={className} {...props} />
  ),
)
Card.displayName = 'Card'
