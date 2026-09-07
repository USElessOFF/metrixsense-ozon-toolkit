import { useEffect, useState } from 'react'

export interface ToastItem {
  id: number
  text: string
  tone: 'ok' | 'error'
}

let nextId = 1
const listeners = new Set<(t: ToastItem) => void>()

export function toast(text: string, tone: ToastItem['tone'] = 'ok') {
  const t: ToastItem = { id: nextId++, text, tone }
  listeners.forEach(l => l(t))
}

export function Toasts() {
  const [items, setItems] = useState<ToastItem[]>([])

  useEffect(() => {
    const add = (t: ToastItem) => {
      setItems(prev => [...prev, t])
      setTimeout(() => setItems(prev => prev.filter(i => i.id !== t.id)), 4000)
    }
    listeners.add(add)
    return () => {
      listeners.delete(add)
    }
  }, [])

  return (
    <div className="toasts">
      {items.map(t => (
        <div key={t.id} className={`toast ${t.tone}`}>
          {t.text}
        </div>
      ))}
    </div>
  )
}
