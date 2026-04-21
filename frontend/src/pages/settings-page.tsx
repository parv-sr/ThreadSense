import { useState, useEffect } from 'react'
import { Sparkles, LogIn, LogOut } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { supabase } from '@/lib/supabase'
import { DirectionAwareTabs } from '@/components/cult/direction-aware-tabs'

export const SettingsPage = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [session, setSession] = useState<any>(null)
  const [activeTab, setActiveTab] = useState('auth')

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

  const tabs = [
    { id: 'auth', label: 'Authentication', icon: <LogIn className='h-4 w-4' /> },
    { id: 'prefs', label: 'Preferences', icon: <Sparkles className='h-4 w-4' /> },
  ]

  return (
    <section className='space-y-6 max-w-3xl'>
      <h1 className='text-2xl font-semibold tracking-tight'>Settings</h1>
      
      <DirectionAwareTabs
        tabs={tabs}
        activeTab={activeTab}
        onChange={setActiveTab}
        className="w-full sm:w-auto self-start"
      />

      {activeTab === 'auth' && (
        <Card className='p-6 text-sm text-zinc-300 animate-in fade-in slide-in-from-bottom-2 duration-300'>
          <div className='mb-6'>
            <h2 className='text-lg font-medium text-zinc-100'>Account Security</h2>
            <p className='text-zinc-500 mt-1'>Manage your session and credentials.</p>
          </div>

          {session ? (
            <div className='flex flex-col items-start gap-4'>
              <div className='flex items-center gap-3 p-4 rounded-xl bg-zinc-900 border border-zinc-800 w-full'>
                <div className="h-10 w-10 rounded-full bg-cyan-900/50 flex items-center justify-center text-cyan-400 font-bold border border-cyan-800/50">
                  {session.user.email?.charAt(0).toUpperCase()}
                </div>
                <div>
                  <p className='text-zinc-400 text-xs'>Logged in as</p>
                  <p className="font-semibold text-zinc-100">{session.user.email}</p>
                </div>
              </div>
              <button onClick={handleLogout} className='flex items-center gap-2 rounded-lg bg-zinc-800 px-4 py-2 hover:bg-red-500/20 hover:text-red-400 text-white transition-colors border border-zinc-700 hover:border-red-500/30'>
                <LogOut className='h-4 w-4' /> Sign out of current session
              </button>
            </div>
          ) : (
            <form onSubmit={handleLogin} className='flex flex-col gap-4 max-w-sm'>
              <div className='space-y-2'>
                <label className='text-xs font-medium text-zinc-400'>Email Address</label>
                <input 
                  type="email" 
                  placeholder="name@example.com" 
                  className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 focus:outline-none focus:border-cyan-500 text-white transition-colors"
                  value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>
              <div className='space-y-2'>
                <label className='text-xs font-medium text-zinc-400'>Password</label>
                <input 
                  type="password" 
                  placeholder="••••••••" 
                  className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 focus:outline-none focus:border-cyan-500 text-white transition-colors"
                  value={password} onChange={(e) => setPassword(e.target.value)} required />
              </div>
              <button type="submit" className='flex items-center justify-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 hover:bg-cyan-500 text-white font-medium transition-colors shadow-lg shadow-cyan-900/20 mt-2'>
                <LogIn className='h-4 w-4' /> Secure Login
              </button>
            </form>
          )}
        </Card>
      )}

      {activeTab === 'prefs' && (
        <Card className='p-6 text-sm text-zinc-300 animate-in fade-in slide-in-from-bottom-2 duration-300'>
          <div className='mb-6'>
            <h2 className='text-lg font-medium text-zinc-100'>Workspace Options</h2>
            <p className='text-zinc-500 mt-1'>Customize your ThreadSense experience.</p>
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-zinc-300 leading-relaxed">
              ThreadSense uses a premium glassmorphic dark theme by default. 
              This interface will soon feature comprehensive controls including:
            </p>
            <ul className="list-disc list-inside mt-3 space-y-1 text-zinc-400">
              <li>LLM Model Selection (GPT-4o, Claude 3.5 Sonnet)</li>
              <li>Custom Extraction Prompts</li>
              <li>Webhook Integrations</li>
            </ul>
          </div>
        </Card>
      )}
    </section>
  )
}
