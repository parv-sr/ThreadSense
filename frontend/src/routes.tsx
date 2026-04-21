import { lazy, Suspense } from 'react'
import { createBrowserRouter, useRouteError } from 'react-router-dom'
import { AppShell } from '@/components/layout/app-shell'

const ChatPage = lazy(() => import('@/pages/chat-page').then(m => ({ default: m.ChatPage })))
const FileDetailsPage = lazy(() => import('@/pages/file-details-page').then(m => ({ default: m.FileDetailsPage })))
const SettingsPage = lazy(() => import('@/pages/settings-page').then(m => ({ default: m.SettingsPage })))
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

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    errorElement: <ErrorBoundary />,
    children: [
      { index: true, element: <SuspenseWrapper><ChatPage /></SuspenseWrapper> },
      { path: 'uploads', element: <SuspenseWrapper><UploadsPage /></SuspenseWrapper> },
      { path: 'uploads/:rawfileId', element: <SuspenseWrapper><FileDetailsPage /></SuspenseWrapper> },
      { path: 'settings', element: <SuspenseWrapper><SettingsPage /></SuspenseWrapper> },
    ],
  },
])
