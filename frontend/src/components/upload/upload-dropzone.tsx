import { useState } from 'react'
import { UploadCloud } from 'lucide-react'
import { Card } from '@/components/ui/card'

export const UploadDropzone = ({ onFileSelect }: { onFileSelect: (file: File) => void }) => {
  const [isDragging, setDragging] = useState(false)

  return (
    <Card
      className={`border-dashed p-10 text-center transition ${isDragging ? 'border-emerald-500 bg-emerald-500/10' : 'border-slate-700'}`}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) onFileSelect(file)
      }}
    >
      <UploadCloud className='mx-auto mb-3 h-12 w-12 text-emerald-400' />
      <p className='mb-2 font-medium'>Drop your WhatsApp export here</p>
      <p className='mb-4 text-sm text-slate-400'>Supports .txt, .zip, and .rar files</p>
      <input
        type='file'
        accept='.txt,.zip,.rar'
        onChange={(e) => e.target.files?.[0] && onFileSelect(e.target.files[0])}
        className='mx-auto block w-full max-w-xs text-sm text-slate-400 file:mr-4 file:rounded-md file:border-0 file:bg-emerald-600 file:px-3 file:py-2 file:text-white'
      />
    </Card>
  )
}
