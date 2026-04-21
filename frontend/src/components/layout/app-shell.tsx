import { Outlet, useNavigation } from 'react-router-dom'
import { Sidebar } from './sidebar'
import { BgAnimatedGradient } from '@/components/cult/bg-animated-gradient'

export const AppShell = () => {
  const navigation = useNavigation()
  const isNavigating = navigation.state === 'loading'

  return (
    <BgAnimatedGradient>
      <div className='mx-auto flex min-h-screen w-full max-w-[1700px] flex-col gap-4 p-3 text-zinc-100 md:flex-row md:p-5 relative z-10'>
        <Sidebar />
        <main className='relative flex-1 overflow-hidden rounded-3xl bg-zinc-950/80 backdrop-blur-2xl border border-zinc-800/50 p-4 md:p-8 shadow-2xl'>
          {isNavigating && (
            <div className="absolute inset-0 z-50 flex items-center justify-center bg-zinc-950/50 backdrop-blur-sm">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-400 border-t-transparent" />
            </div>
          )}
          <Outlet />
        </main>
      </div>
    </BgAnimatedGradient>
  )
}
