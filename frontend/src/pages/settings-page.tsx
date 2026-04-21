import { useState, useEffect } from 'react'
import { Sparkles, LogIn, LogOut } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { supabase } from '@/lib/supabase'

export const SettingsPage = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [session, setSession] = useState<any>(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => setSession(session))
    supabase.auth.onAuthStateChange((_event, session) => setSession(session))
  }, [])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    await supabase.auth.signInWithPassword({ email, password })
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
  }

  return (
    <section className='space-y-4'>
      <h1 className='text-2xl font-semibold tracking-tight'>Settings</h1>
      
      <Card className='p-5 text-sm text-zinc-300'>
        <div className='mb-3 flex items-center gap-2 text-cyan-200'>
          <Sparkles className='h-4 w-4' />
          <p className='font-medium text-zinc-100'>Authentication</p>
        </div>
        {session ? (
          <div className='flex flex-col items-start gap-4'>
            <p>Logged in as: <span className="font-semibold text-white">{session.user.email}</span></p>
            <button onClick={handleLogout} className='flex items-center gap-2 rounded bg-zinc-800 px-4 py-2 hover:bg-zinc-700 text-white'>
              <LogOut className='h-4 w-4' /> Logout
            </button>
          </div>
        ) : (
          <form onSubmit={handleLogin} className='flex flex-col gap-3 max-w-sm'>
            <input 
              type="email" 
              placeholder="Email" 
              className="px-3 py-2 rounded bg-zinc-900 border border-zinc-800 focus:outline-none focus:border-cyan-500 text-white"
              value={email} onChange={(e) => setEmail(e.target.value)} required />
            <input 
              type="password" 
              placeholder="Password" 
              className="px-3 py-2 rounded bg-zinc-900 border border-zinc-800 focus:outline-none focus:border-cyan-500 text-white"
              value={password} onChange={(e) => setPassword(e.target.value)} required />
            <button type="submit" className='flex items-center justify-center gap-2 rounded bg-cyan-600 px-4 py-2 hover:bg-cyan-500 text-white font-medium'>
              <LogIn className='h-4 w-4' /> Login
            </button>
          </form>
        )}
      </Card>

      <Card className='p-5 text-sm text-zinc-300'>
        <div className='mb-3 flex items-center gap-2 text-cyan-200'>
          <Sparkles className='h-4 w-4' />
          <p className='font-medium text-zinc-100'>Workspace preferences</p>
        </div>
        ThreadSense uses a premium glassmorphic dark theme by default. This page is ready for future controls such as model
        settings, API endpoint overrides, and persona tuning.
      </Card>
    </section>
  )
}
