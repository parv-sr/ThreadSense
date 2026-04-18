import { Link, useLocation } from 'react-router-dom'
import { BrainCircuit, MessageSquareText, Settings, Upload } from 'lucide-react'
import { cn } from '@/lib/utils'

const nav = [
  { to: '/', label: 'Chat', icon: MessageSquareText },
  { to: '/uploads', label: 'Uploads', icon: Upload },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export const Sidebar = () => {
  const location = useLocation()

  return (
    <aside className='tactile-panel w-full rounded-3xl p-4 md:h-[calc(100vh-2.5rem)] md:w-72 md:p-5'>
      <div className='mb-8 flex items-center gap-3'>
        <div className='rounded-xl border border-zinc-800 bg-zinc-900 p-2 text-cyan-300'>
          <BrainCircuit className='h-5 w-5' />
        </div>
        <div>
          <p className='text-lg font-semibold'>ThreadSense</p>
          <p className='font-mono-data text-xs text-zinc-500'>TACTILE DARK · v1</p>
        </div>
      </div>

      <nav className='flex gap-2 md:flex-col'>
        {nav.map((item) => {
          const Icon = item.icon
          const active = location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)
          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                'flex flex-1 items-center gap-2 rounded-xl border px-3 py-2.5 text-sm transition md:flex-none',
                active
                  ? 'border-cyan-400/50 bg-zinc-900 text-cyan-200'
                  : 'border-transparent text-zinc-300 hover:border-zinc-700 hover:bg-zinc-900 hover:text-zinc-100',
              )}
            >
              <Icon className='h-4 w-4' />
              {item.label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
