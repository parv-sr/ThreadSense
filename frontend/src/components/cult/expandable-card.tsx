import * as React from 'react'
import { cn } from '@/lib/utils'

export const ExpandableCard = ({
  title,
  subtitle,
  children,
  className,
  expanded = false,
}: {
  title: string
  subtitle?: React.ReactNode
  children?: React.ReactNode
  className?: string
  expanded?: boolean
}) => {
  const [isExpanded, setIsExpanded] = React.useState(expanded)

  return (
    <div className={cn('rounded-xl border border-zinc-800 bg-zinc-950/80 p-4 transition-all duration-300', className)}>
      <div 
        className='flex cursor-pointer items-center justify-between'
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div>
          <h3 className='font-medium text-zinc-100'>{title}</h3>
          {subtitle && <div className='text-sm text-zinc-400 mt-1'>{subtitle}</div>}
        </div>
        <div className='flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900 text-zinc-400 transition-transform duration-300' style={{ transform: isExpanded ? 'rotate(180deg)' : 'none' }}>
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3.13523 6.15803C3.3241 5.95657 3.64052 5.94637 3.84197 6.13523L7.5 9.56464L11.158 6.13523C11.3595 5.94637 11.6759 5.95657 11.8648 6.15803C12.0536 6.35949 12.0434 6.67591 11.842 6.86477L7.84197 10.6148C7.64964 10.7951 7.35036 10.7951 7.15803 10.6148L3.15803 6.86477C2.95657 6.67591 2.94637 6.35949 3.13523 6.15803Z" fill="currentColor" fillRule="evenodd" clipRule="evenodd"></path></svg>
        </div>
      </div>
      <div className={cn('overflow-hidden transition-all duration-300', isExpanded ? 'max-h-[1000px] mt-4 opacity-100' : 'max-h-0 opacity-0')}>
        {children}
      </div>
    </div>
  )
}
