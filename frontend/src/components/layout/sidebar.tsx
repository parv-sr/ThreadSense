import { Link, useLocation } from 'react-router-dom'
import { MessageSquareText, Upload, Settings, BrainCircuit } from 'lucide-react'
import { cn } from '@/lib/utils'

const nav = [
  { to: '/', label: 'Chat', icon: MessageSquareText },
  { to: '/uploads', label: 'Uploads', icon: Upload },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export const Sidebar = () => {
  const location = useLocation()

  return (
    <aside className='w-full border-b border-slate-800 bg-slate-950 p-4 md:h-screen md:w-72 md:border-b-0 md:border-r'>
      <div className='mb-6 flex items-center gap-3'>
        <div className='rounded-lg bg-emerald-600/20 p-2 text-emerald-400'><BrainCircuit /></div>
        <div>
          <p className='text-lg font-semibold text-slate-100'>ThreadSense</p>
          <p className='text-xs text-slate-400'>v2 Intelligence Workspace</p>
        </div>
      </div>
      <nav className='flex gap-2 md:flex-col'>
        {nav.map((item) => {
          const Icon = item.icon
          const active = location.pathname === item.to
          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                'flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-sm transition md:flex-none',
                active ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800',
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
