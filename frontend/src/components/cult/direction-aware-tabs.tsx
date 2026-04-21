import * as React from 'react'
import { cn } from '@/lib/utils'

export const DirectionAwareTabs = ({
  tabs,
  activeTab,
  onChange,
  className,
}: {
  tabs: { id: string; label: string; icon?: React.ReactNode }[]
  activeTab: string
  onChange: (id: string) => void
  className?: string
}) => {
  return (
    <div className={cn('flex items-center gap-2 rounded-xl bg-zinc-900/50 p-1 backdrop-blur-md', className)}>
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={cn(
              'relative flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-200',
              isActive ? 'text-zinc-50 shadow-sm' : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
            )}
          >
            {isActive && (
              <span className='absolute inset-0 rounded-lg bg-zinc-800 shadow-[0_0_15px_rgba(0,0,0,0.5)]' />
            )}
            <span className='relative z-10 flex items-center gap-2'>
              {tab.icon}
              {tab.label}
            </span>
          </button>
        )
      })}
    </div>
  )
}
