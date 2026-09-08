import type { ReactNode } from 'react'

export function Card({
  title,
  actions,
  children,
  className,
}: {
  title?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`card ${className ?? ''}`}>
      {(title || actions) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

export function PageHead({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <p className="page-sub">{sub}</p>}
      </div>
      {actions}
    </div>
  )
}

export function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      {hint && <span className="kpi-hint">{hint}</span>}
    </div>
  )
}

const TONE_CLASS: Record<string, string> = {
  critical: 'bad',
  high: 'warn',
  medium: 'mid',
  low: 'dim',
  ok: 'ok',
  error: 'bad',
  warn: 'warn',
  info: 'dim',
}

export function Badge({ tone, children }: { tone: string; children: ReactNode }) {
  return <span className={`badge ${TONE_CLASS[tone] ?? 'dim'}`}>{children}</span>
}

export function Spinner() {
  return <span className="spinner" aria-label="Загрузка" />
}

export function Loading({ text = 'Загрузка…' }: { text?: string }) {
  return (
    <div className="state">
      <Spinner /> {text}
    </div>
  )
}

export function Empty({ text }: { text: string }) {
  return <div className="state">{text}</div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state error">
      <p>{message}</p>
      {onRetry && (
        <button className="btn" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  )
}

export function Warnings({ items }: { items: string[] }) {
  if (items.length === 0) return null
  return (
    <div className="warnings">
      {items.map((w, i) => (
        <p key={i}>{w}</p>
      ))}
    </div>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  )
}

export function ScoreBar({ value, max = 100 }: { value: number | null; max?: number }) {
  if (value === null) return <span>—</span>
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <span className="scorebar">
      <span style={{ width: `${pct}%` }} />
      <em>{max === 1 ? Math.round(value * 100) / 100 : Math.round(value)}</em>
    </span>
  )
}
