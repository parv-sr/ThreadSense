import { Outlet, useNavigation } from 'react-router-dom'
import { Sidebar } from './sidebar'

export const AppShell = () => {
  const navigation = useNavigation()
  const isNavigating = navigation.state === 'loading'

  return (
    <div className='min-h-screen bg-zinc-950 text-zinc-100'>
      <div className='mx-auto flex min-h-screen w-full max-w-[1800px] flex-col gap-4 p-3 md:flex-row md:p-5'>
      <Sidebar />
      <main className='relative flex-1 overflow-hidden border border-zinc-800 bg-zinc-950 p-4 md:p-6'>
        {isNavigating && (
          <div className='absolute inset-0 z-50 flex items-center justify-center bg-zinc-950/60 backdrop-blur-sm'>
            <div className='h-8 w-8 animate-spin rounded-full border-4 border-cyan-400 border-t-transparent' />
          </div>
        )}
        <Outlet />
      </main>
      </div>
    </div>
  )
}
