import * as React from "react"
export const Badge = ({ children }: { children: React.ReactNode }) => (
  <span className='rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300'>
    {children}
  </span>
)
