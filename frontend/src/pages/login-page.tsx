import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { BrainCircuit, Eye, EyeOff, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/lib/auth'

export const LoginPage = () => {
  const { isAuthenticated, isLoading, login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  if (isLoading) {
    return (
      <div className='flex min-h-screen items-center justify-center bg-zinc-950'>
        <div className='h-8 w-8 animate-spin rounded-full border-4 border-cyan-400 border-t-transparent' />
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to='/search' replace />
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return
    setSubmitting(true)
    try {
      await login(username.trim(), password)
      toast.success('Logged in successfully.')
    } catch {
      // Error toast handled by axios interceptor
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className='flex min-h-screen items-center justify-center bg-zinc-950 px-4'>
      <div className='w-full max-w-sm'>
        {/* Logo */}
        <div className='mb-8 flex flex-col items-center'>
          <div className='mb-3 rounded-xl border border-zinc-800 bg-zinc-900 p-3 text-cyan-300'>
            <BrainCircuit className='h-8 w-8' />
          </div>
          <h1 className='text-2xl font-bold text-zinc-100'>ThreadSense</h1>
          <p className='mt-1 text-sm text-zinc-500'>
            Sign in to continue
          </p>
        </div>

        <form onSubmit={handleSubmit} className='space-y-4'>
          <div>
            <label htmlFor='username' className='mb-1 block text-sm font-medium text-zinc-300'>
              Username
            </label>
            <input
              id='username'
              type='text'
              autoComplete='username'
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className='w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2.5 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30'
              placeholder='Enter username'
              required
              minLength={3}
            />
          </div>

          <div>
            <label htmlFor='password' className='mb-1 block text-sm font-medium text-zinc-300'>
              Password
            </label>
            <div className='relative'>
              <input
                id='password'
                type={showPassword ? 'text' : 'password'}
                autoComplete='current-password'
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className='w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2.5 pr-10 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30'
                placeholder='Enter password'
                required
                minLength={4}
              />
              <button
                type='button'
                onClick={() => setShowPassword(!showPassword)}
                className='absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300'
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className='h-4 w-4' /> : <Eye className='h-4 w-4' />}
              </button>
            </div>
          </div>

          <button
            type='submit'
            disabled={submitting}
            className='flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-400 disabled:opacity-50'
          >
            {submitting && <Loader2 className='h-4 w-4 animate-spin' />}
            Sign In
          </button>
        </form>

        <p className='mt-6 text-center text-xs text-zinc-600'>
          Self-hosted instance · SQL filters first, vectors second.
        </p>
      </div>
    </div>
  )
}
