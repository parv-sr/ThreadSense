import { Link, useLocation } from 'react-router-dom'
import { BrainCircuit, Database, MessageSquareText, Settings, Upload } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/lib/auth'

const nav = [
  { to: '/search', label: 'Search', icon: Database },
  { to: '/chat', label: 'Chat', icon: MessageSquareText },
  { to: '/uploads', label: 'Uploads', icon: Upload },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export const Sidebar = () => {
  const location = useLocation()
  const { user } = useAuth()

  return (
    <aside className='flex w-full flex-col justify-between border border-zinc-800 bg-zinc-950 p-4 md:h-[calc(100vh-2.5rem)] md:w-64 md:p-5'>
      <div>
        <div className='mb-8 flex items-center gap-3'>
          <div className='rounded-md border border-zinc-800 bg-zinc-900 p-2 text-cyan-300'>
            <BrainCircuit className='h-5 w-5' />
          </div>
          <div>
            <p className='text-lg font-semibold text-zinc-100'>ThreadSense</p>
            <p className='text-xs text-zinc-500'>Postgres inventory</p>
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
                  'flex flex-1 items-center gap-3 rounded-md border px-3 py-2.5 text-sm font-medium transition-colors md:flex-none',
                  active
                    ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-100'
                    : 'border-transparent text-zinc-400 hover:border-zinc-800 hover:bg-zinc-900 hover:text-zinc-100',
                )}
              >
                <Icon className={cn('h-4 w-4', active ? 'text-cyan-300' : 'text-zinc-500')} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>
      </div>

      <div className='hidden space-y-2 border-t border-zinc-800 pt-4 md:block'>
        {user && (
          <p className='text-sm text-zinc-300 truncate' title={user.username}>
            {user.display_name || user.username}
          </p>
        )}
        <p className='text-xs text-zinc-600'>SQL filters first. Vectors second.</p>
      </div>
    </aside>
  )
}
