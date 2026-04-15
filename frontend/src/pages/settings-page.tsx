import { Sparkles } from 'lucide-react'
import { Card } from '@/components/ui/card'

export const SettingsPage = () => (
  <section className='space-y-4'>
    <h1 className='text-2xl font-semibold tracking-tight'>Settings</h1>
    <Card className='p-5 text-sm text-slate-300'>
      <div className='mb-3 flex items-center gap-2 text-cyan-200'>
        <Sparkles className='h-4 w-4' />
        <p className='font-medium text-slate-100'>Workspace preferences</p>
      </div>
      ThreadSense uses a premium glassmorphic dark theme by default. This page is ready for future controls such as model
      settings, API endpoint overrides, and persona tuning.
    </Card>
  </section>
)
