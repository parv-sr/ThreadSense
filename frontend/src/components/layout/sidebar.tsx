import { Link, useLocation } from 'react-router-dom'
import { BrainCircuit, MessageSquareText, Settings, Upload } from 'lucide-react'
import { cn } from '@/lib/utils'
import { TextShimmer } from '@/components/cult/text-shimmer'
import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'

const nav = [
  { to: '/', label: 'Chat', icon: MessageSquareText },
  { to: '/uploads', label: 'Uploads', icon: Upload },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export const Sidebar = () => {
  const location = useLocation()
  const [email, setEmail] = useState<string | null>(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setEmail(session?.user?.email ?? null)
    })
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user?.email ?? null)
    })
    return () => subscription.unsubscribe()
  }, [])

  return (
    <aside className='flex w-full flex-col justify-between rounded-3xl backdrop-blur-xl bg-zinc-950/80 border-r border-zinc-800/50 p-4 md:h-[calc(100vh-2.5rem)] md:w-72 md:p-5 shadow-xl transition-all'>
      <div>
        <div className='mb-8 flex items-center gap-3'>
          <div className='rounded-xl border border-zinc-800 bg-zinc-900 p-2 text-cyan-300 shadow-[0_0_15px_rgba(34,211,238,0.3)]'>
            <BrainCircuit className='h-5 w-5' />
          </div>
          <div>
            <TextShimmer className='text-lg font-bold'>ThreadSense</TextShimmer>
            <p className='text-xs text-zinc-400 font-medium'>Intelligence Workspace</p>
          </div>
        </div>

        <nav className='flex gap-2 md:flex-col'>
          {nav.map((item) => {
            const Icon = item.icon
            const active = item.to === '/'
              ? location.pathname === '/'
              : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)
              
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  'relative flex flex-1 items-center gap-3 rounded-xl px-4 py-3 text-sm transition-all md:flex-none font-medium',
                  active
                    ? 'bg-zinc-900 text-cyan-200 border border-cyan-500/30 shadow-[0_0_20px_rgba(34,211,238,0.1)]'
                    : 'border border-transparent text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/50',
                )}
              >
                {active && (
                  <span className='absolute inset-0 rounded-xl bg-gradient-to-r from-cyan-500/10 to-transparent opacity-50' />
                )}
                <Icon className={cn('h-5 w-5 relative z-10 transition-colors', active ? 'text-cyan-400' : 'text-zinc-500')} />
                <span className='relative z-10'>{item.label}</span>
              </Link>
            )
          })}
        </nav>
      </div>
      
      <div className='hidden md:block mt-8 pt-4 border-t border-zinc-800/50'>
        <div className='flex items-center gap-3'>
          <div className='flex h-9 w-9 items-center justify-center rounded-full bg-cyan-950 border border-cyan-800/50 text-cyan-200 font-bold text-xs'>
            {email ? email.charAt(0).toUpperCase() : '?'}
          </div>
          <div className='flex flex-col overflow-hidden'>
            <span className='text-sm font-medium text-zinc-200 truncate'>
              {email ? 'Authenticated' : 'Guest Session'}
            </span>
            <span className='text-xs text-zinc-500 truncate'>
              {email ?? 'Not signed in'}
            </span>
          </div>
        </div>
      </div>
    </aside>
  )
}
