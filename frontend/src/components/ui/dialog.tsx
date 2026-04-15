import * as React from 'react'
import { X } from 'lucide-react'

interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  children: React.ReactNode
}

export const Dialog = ({ open, onOpenChange, title, children }: DialogProps) => {
  if (!open) return null

  return (
    <div className='fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm'>
      <div className='glass-panel relative w-full max-w-3xl rounded-2xl p-6'>
        <button
          className='absolute right-4 top-4 rounded-md p-1 text-slate-300 transition hover:bg-white/10 hover:text-white'
          onClick={() => onOpenChange(false)}
        >
          <X className='h-4 w-4' />
        </button>
        <h2 className='mb-4 text-lg font-semibold text-slate-100'>{title}</h2>
        {children}
      </div>
    </div>
  )
}
