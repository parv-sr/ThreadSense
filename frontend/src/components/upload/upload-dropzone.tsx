import { useRef, useState } from 'react'
import { FileArchive, UploadCloud } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

export const UploadDropzone = ({ onFileSelect }: { onFileSelect: (file: File) => void }) => {
  const [isDragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)

  return (
    <Card
      className={`relative overflow-hidden border-2 border-dashed p-12 text-center transition-all duration-200 ${
        isDragging
          ? 'border-cyan-400 bg-zinc-900 shadow-[0_0_0_1px_rgba(34,211,238,0.45)]'
          : 'border-zinc-700 bg-zinc-950 hover:border-zinc-600'
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
      {isDragging ? <div className='absolute inset-0 bg-black/35' /> : null}
      <div className='relative z-10'>
        <UploadCloud className='mx-auto mb-3 h-12 w-12 text-cyan-300' />
        <p className='mb-2 text-xl font-semibold'>Drop your WhatsApp export here</p>
        <p className='mb-5 text-sm text-zinc-400'>Supports .txt, .zip, and .rar files</p>
        <Button type='button' variant='secondary' onClick={() => inputRef.current?.click()}>
          <FileArchive className='mr-2 h-4 w-4' /> Browse Files
        </Button>
        <input
          ref={inputRef}
          type='file'
          accept='.txt,.zip,.rar'
          onChange={(e) => e.target.files?.[0] && onFileSelect(e.target.files[0])}
          className='hidden'
        />
      </div>
    </Card>
  )
}
