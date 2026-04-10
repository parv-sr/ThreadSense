import { Outlet } from 'react-router-dom'
import { Sidebar } from './sidebar'

export const AppShell = () => (
  <div className='min-h-screen bg-slate-950 text-slate-100 md:flex'>
    <Sidebar />
    <main className='flex-1 p-4 md:p-8'>
      <Outlet />
    </main>
  </div>
)
