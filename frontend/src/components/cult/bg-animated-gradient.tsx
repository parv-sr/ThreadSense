import { cn } from '@/lib/utils'

export const BgAnimatedGradient = ({
  className,
  children,
}: {
  className?: string
  children?: React.ReactNode
}) => (
  <div
    className={cn(
      'relative h-full w-full bg-zinc-950 overflow-hidden',
      className
    )}
  >
    <div className='absolute inset-0 overflow-hidden pointer-events-none'>
      <div className='absolute -top-[40%] -left-[10%] w-[70%] h-[70%] rounded-full bg-cyan-900/20 blur-[120px] animate-pulse' style={{ animationDuration: '8s' }} />
      <div className='absolute -bottom-[40%] -right-[10%] w-[70%] h-[70%] rounded-full bg-blue-900/20 blur-[120px] animate-pulse' style={{ animationDuration: '12s', animationDelay: '2s' }} />
    </div>
    <div className='relative z-10 h-full w-full'>{children}</div>
  </div>
)
