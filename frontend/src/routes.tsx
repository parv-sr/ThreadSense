import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, useRouteError } from 'react-router-dom'
import { AppShell } from '@/components/layout/app-shell'
import { useAuth } from '@/lib/auth'

const ChatPage = lazy(() => import('@/pages/chat-page').then(m => ({ default: m.ChatPage })))
const FileDetailsPage = lazy(() => import('@/pages/file-details-page').then(m => ({ default: m.FileDetailsPage })))
const LoginPage = lazy(() => import('@/pages/login-page').then(m => ({ default: m.LoginPage })))
const SettingsPage = lazy(() => import('@/pages/settings-page').then(m => ({ default: m.SettingsPage })))
const SearchPage = lazy(() => import('@/pages/search-page').then(m => ({ default: m.SearchPage })))
const UploadsPage = lazy(() => import('@/pages/uploads-page').then(m => ({ default: m.UploadsPage })))

const ErrorBoundary = () => {
  const error = useRouteError() as any
  return (
    <div className="flex h-full w-full flex-col items-center justify-center p-8 text-center text-zinc-100">
      <h1 className="mb-4 text-4xl font-bold text-red-500">Oops!</h1>
      <p className="mb-4 text-lg text-zinc-300">Something went wrong.</p>
      <pre className="rounded bg-zinc-900 p-4 text-sm text-red-400">
        {error?.message || 'Unknown error'}
      </pre>
    </div>
  )
}

const SuspenseWrapper = ({ children }: { children: React.ReactNode }) => (
  <Suspense fallback={<div className="flex h-full items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-400 border-t-transparent" /></div>}>
    {children}
  </Suspense>
)

const AuthGuard = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className='flex min-h-screen items-center justify-center bg-zinc-950'>
        <div className='h-8 w-8 animate-spin rounded-full border-4 border-cyan-400 border-t-transparent' />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to='/login' replace />
  }

  return <>{children}</>
}

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <SuspenseWrapper><LoginPage /></SuspenseWrapper>,
    errorElement: <ErrorBoundary />,
  },
  {
    path: '/',
    element: (
      <AuthGuard>
        <AppShell />
      </AuthGuard>
    ),
    errorElement: <ErrorBoundary />,
    children: [
      { index: true, element: <Navigate to='/search' replace /> },
      { path: 'search', element: <SuspenseWrapper><SearchPage /></SuspenseWrapper> },
      { path: 'chat', element: <SuspenseWrapper><ChatPage /></SuspenseWrapper> },
      { path: 'uploads', element: <SuspenseWrapper><UploadsPage /></SuspenseWrapper> },
      { path: 'uploads/:rawfileId', element: <SuspenseWrapper><FileDetailsPage /></SuspenseWrapper> },
      { path: 'settings', element: <SuspenseWrapper><SettingsPage /></SuspenseWrapper> },
    ],
  },
])
