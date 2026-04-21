import { cn } from '@/lib/utils'

export const BgGrid = ({
  className,
  children,
}: {
  className?: string
  children?: React.ReactNode
}) => (
  <div className={cn('relative h-full w-full bg-zinc-950', className)}>
    <div className='absolute inset-0 bg-[linear-gradient(to_right,#4f4f4f2e_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f2e_1px,transparent_1px)] bg-[size:14px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]' />
    <div className="relative z-10 h-full">{children}</div>
  </div>
)
