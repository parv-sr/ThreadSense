import { useCallback, useRef, useState } from 'react'
import { uploadFile, pollUntilDone, type TaskStatusResponse } from '../services/api'

type UploadState =
  | { phase: 'idle' }
  | { phase: 'uploading' }
  | { phase: 'polling'; taskId: string }
  | { phase: 'done'; result: TaskStatusResponse }
  | { phase: 'error'; message: string }

interface UploadZoneProps {
  onComplete?: (result: TaskStatusResponse) => void
}

export default function UploadZone({ onComplete }: UploadZoneProps) {
  const [state, setState] = useState<UploadState>({ phase: 'idle' })
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const processFile = useCallback(
    async (file: File) => {
      const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
      if (!['txt', 'zip', 'rar'].includes(ext)) {
        setState({ phase: 'error', message: 'Only .txt, .zip, and .rar files are accepted.' })
        return
      }

      setState({ phase: 'uploading' })
      try {
        const ingestRes = await uploadFile(file)
        if (ingestRes.status === 'ALREADY_EXISTS') {
          const result: TaskStatusResponse = {
            status: 'COMPLETED',
            task_id: ingestRes.task_id,
            result: { rawfile_id: ingestRes.rawfile_id, note: 'Already processed previously.' },
          }
          setState({ phase: 'done', result })
          onComplete?.(result)
          return
        }

        setState({ phase: 'polling', taskId: ingestRes.task_id })
        const final = await pollUntilDone(ingestRes.task_id)
        setState({ phase: 'done', result: final })
        onComplete?.(final)
      } catch (err) {
        setState({ phase: 'error', message: err instanceof Error ? err.message : 'Upload failed' })
      }
    },
    [onComplete],
  )

  return (
    <div
      role='button'
      tabIndex={0}
      className={`relative flex min-h-[300px] w-full max-w-3xl flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-10 text-center font-mono-data transition-all ${
        dragging ? 'border-cyan-400 bg-zinc-900' : 'border-zinc-700 bg-zinc-950'
      }`}
      onClick={() => (state.phase === 'idle' ? inputRef.current?.click() : undefined)}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) processFile(file)
      }}
    >
      {dragging ? <div className='absolute inset-0 rounded-2xl bg-black/35' /> : null}
      <input
        ref={inputRef}
        type='file'
        accept='.txt,.zip,.rar'
        className='hidden'
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) processFile(file)
          e.target.value = ''
        }}
      />
      <p className='relative z-10 text-lg text-zinc-100'>
        {state.phase === 'idle' && 'Drop a WhatsApp export here, or click to browse'}
        {state.phase === 'uploading' && 'Uploading...'}
        {state.phase === 'polling' && `Processing task ${state.taskId}...`}
        {state.phase === 'done' && 'Pipeline complete ✓'}
        {state.phase === 'error' && state.message}
      </p>
    </div>
  )
}
