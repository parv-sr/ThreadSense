import { useRef, useState } from 'react'
import { FileArchive, UploadCloud } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

export const UploadDropzone = ({ onFileSelect }: { onFileSelect: (file: File) => void }) => {
  const [isDragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)

  return (
    <Card
      className={`border-dashed p-8 text-center transition ${
        isDragging ? 'border-cyan-300/50 bg-cyan-400/10' : 'border-white/20 bg-slate-900/40'
      }`}
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
      <UploadCloud className='mx-auto mb-3 h-12 w-12 text-cyan-200' />
      <p className='mb-2 text-lg font-medium'>Drop your WhatsApp export here</p>
      <p className='mb-5 text-sm text-slate-400'>Supports .txt, .zip, and .rar files</p>
      <div className='mb-4 transition hover:-translate-y-0.5'>
        <Button type='button' variant='secondary' onClick={() => inputRef.current?.click()}>
          <FileArchive className='mr-2 h-4 w-4' /> Browse Files
        </Button>
      </div>
      <input
        ref={inputRef}
        type='file'
        accept='.txt,.zip,.rar'
        onChange={(e) => e.target.files?.[0] && onFileSelect(e.target.files[0])}
        className='hidden'
      />
      <p className='text-xs text-slate-500'>Tip: drag & drop for fastest upload.</p>
    </Card>
  )
}
