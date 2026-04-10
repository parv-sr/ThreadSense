import { Card } from '@/components/ui/card'

export const SettingsPage = () => (
  <section className='space-y-4'>
    <h1 className='text-2xl font-semibold'>Settings</h1>
    <Card className='p-4 text-sm text-slate-300'>
      ThreadSense v2 uses a WhatsApp-inspired dark theme by default. Advanced settings can be connected here later (model settings, API endpoint overrides, persona tuning).
    </Card>
  </section>
)
