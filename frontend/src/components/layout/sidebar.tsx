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
    <aside className='glass-panel w-full rounded-3xl p-4 md:h-[calc(100vh-2.5rem)] md:w-72 md:p-5'>
      <div className='mb-8 flex items-center gap-3'>
        <div className='rounded-xl border border-cyan-300/30 bg-cyan-400/10 p-2 text-cyan-200'>
          <BrainCircuit className='h-5 w-5' />
        </div>
        <div>
          <p className='text-lg font-semibold'>ThreadSense</p>
          <p className='text-xs text-slate-400'>Intelligence Workspace</p>
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
                'flex flex-1 items-center gap-2 rounded-xl border px-3 py-2.5 text-sm transition duration-200 md:flex-none',
                active
                  ? 'border-cyan-300/35 bg-cyan-400/10 text-white'
                  : 'border-transparent text-slate-300 hover:-translate-y-0.5 hover:border-white/10 hover:bg-white/5 hover:text-slate-100',
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
