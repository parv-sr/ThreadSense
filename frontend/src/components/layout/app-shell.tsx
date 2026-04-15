import { Outlet } from 'react-router-dom'
import { Sidebar } from './sidebar'

export const AppShell = () => (
  <div className='mx-auto flex min-h-screen w-full max-w-[1600px] flex-col gap-4 p-3 text-slate-100 md:flex-row md:p-5'>
    <Sidebar />
    <main className='glass-panel relative flex-1 overflow-hidden rounded-3xl p-4 md:p-8'>
      <div className='pointer-events-none absolute inset-0 -z-10 opacity-60 [background:linear-gradient(120deg,rgba(59,130,246,0.08),transparent_40%,rgba(56,189,248,0.08))]' />
      <Outlet />
    </main>
  </div>
)
