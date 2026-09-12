import { isoDay } from '../lib/format'

interface Props {
  from: string
  to: string
  onChange: (range: { date_from: string; date_to: string }) => void
  busy?: boolean
}

const QUICK = [7, 30, 90]

export function PeriodPicker({ from, to, onChange }: Props) {
  const quick = (days: number) => {
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - days)
    onChange({ date_from: isoDay(start), date_to: isoDay(end) })
  }

  return (
    <div className="period">
      {QUICK.map(d => (
        <button key={d} type="button" className="btn ghost tiny" onClick={() => quick(d)}>
          {d} дн
        </button>
      ))}
      <input
        type="date"
        className="input"
        value={from}
        max={to}
        onChange={e => onChange({ date_from: e.target.value, date_to: to })}
      />
      <span className="period-dash">—</span>
      <input
        type="date"
        className="input"
        value={to}
        min={from}
        onChange={e => onChange({ date_from: from, date_to: e.target.value })}
      />
    </div>
  )
}
