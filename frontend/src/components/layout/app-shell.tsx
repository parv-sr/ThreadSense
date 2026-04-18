import { Outlet } from 'react-router-dom'
import { Sidebar } from './sidebar'

export const AppShell = () => (
  <div className='font-ui mx-auto flex min-h-screen w-full max-w-[1700px] flex-col gap-4 bg-zinc-950 p-3 text-zinc-100 md:flex-row md:p-5'>
    <Sidebar />
    <main className='tactile-panel relative flex-1 overflow-hidden rounded-3xl p-4 md:p-8'>
      <Outlet />
    </main>
  </div>
)
