import { useState } from 'react'
import { KeyRound, LogOut, ServerCog, User } from 'lucide-react'
import { toast } from 'sonner'
import { Card } from '@/components/ui/card'
import { env } from '@/lib/env'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'

export const SettingsPage = () => {
  const { user, logout, refreshUser } = useAuth()
  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [saving, setSaving] = useState(false)

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const body: Record<string, string> = {}
      if (displayName.trim() && displayName !== user?.display_name) {
        body.display_name = displayName.trim()
      }
      if (newPassword) {
        if (!currentPassword) {
          toast.error('Current password is required to set a new password.')
          setSaving(false)
          return
        }
        body.current_password = currentPassword
        body.new_password = newPassword
      }
      if (Object.keys(body).length === 0) {
        toast.info('No changes to save.')
        setSaving(false)
        return
      }
      await api.put('/auth/me', body)
      await refreshUser()
      setCurrentPassword('')
      setNewPassword('')
      toast.success('Profile updated.')
    } catch {
      // error handled by interceptor
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className='max-w-3xl space-y-6'>
      <div>
        <h1 className='text-2xl font-semibold'>Settings</h1>
        <p className='text-sm text-zinc-500'>Manage your account and view system configuration.</p>
      </div>

      {/* User Profile */}
      <Card className='rounded-md border-zinc-800 bg-zinc-950 p-5'>
        <div className='mb-4 flex items-center gap-3'>
          <div className='rounded-md border border-zinc-800 bg-zinc-900 p-2 text-cyan-300'>
            <User className='h-4 w-4' />
          </div>
          <div>
            <p className='font-medium text-zinc-100'>Account</p>
            <p className='text-sm text-zinc-500'>
              Logged in as <span className='font-mono text-zinc-300'>{user?.username}</span>
            </p>
          </div>
        </div>

        <form onSubmit={handleUpdateProfile} className='space-y-4'>
          <div>
            <label htmlFor='displayName' className='mb-1 block text-sm font-medium text-zinc-400'>
              Display Name
            </label>
            <input
              id='displayName'
              type='text'
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className='w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-cyan-500/50'
            />
          </div>

          <div className='border-t border-zinc-800 pt-4'>
            <div className='mb-3 flex items-center gap-2'>
              <KeyRound className='h-4 w-4 text-zinc-500' />
              <p className='text-sm font-medium text-zinc-400'>Change Password</p>
            </div>
            <div className='grid gap-3 sm:grid-cols-2'>
              <input
                type='password'
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder='Current password'
                autoComplete='current-password'
                className='rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none placeholder:text-zinc-600 focus:border-cyan-500/50'
              />
              <input
                type='password'
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder='New password'
                autoComplete='new-password'
                minLength={4}
                className='rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none placeholder:text-zinc-600 focus:border-cyan-500/50'
              />
            </div>
          </div>

          <button
            type='submit'
            disabled={saving}
            className='rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-400 disabled:opacity-50'
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </form>
      </Card>

      {/* System Info */}
      <Card className='rounded-md border-zinc-800 bg-zinc-950 p-5'>
        <div className='mb-4 flex items-center gap-3'>
          <div className='rounded-md border border-zinc-800 bg-zinc-900 p-2 text-cyan-300'>
            <ServerCog className='h-4 w-4' />
          </div>
          <div>
            <p className='font-medium text-zinc-100'>System</p>
            <p className='font-mono-data text-sm text-zinc-500'>{env.apiUrl}</p>
          </div>
        </div>
        <div className='grid gap-3 text-sm text-zinc-400 sm:grid-cols-2'>
          <div className='rounded-lg border border-zinc-800 p-3'>
            <p className='text-zinc-500'>Database</p>
            <p className='mt-1 text-zinc-200'>PostgreSQL + pgvector</p>
          </div>
          <div className='rounded-lg border border-zinc-800 p-3'>
            <p className='text-zinc-500'>LLM Gateway</p>
            <p className='mt-1 text-zinc-200'>OpenRouter</p>
          </div>
        </div>
      </Card>

      {/* Logout */}
      <button
        onClick={logout}
        className='flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-medium text-red-400 transition hover:bg-red-500/20'
      >
        <LogOut className='h-4 w-4' />
        Sign Out
      </button>
    </section>
  )
}
