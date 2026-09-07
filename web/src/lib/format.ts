const money = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 })
const int = new Intl.NumberFormat('ru-RU')

export function fmtMoney(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return `${money.format(v)} ₽`
}

export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(digits).replace('.', ',')
}

export function fmtInt(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return int.format(v)
}

export function fmtPercent(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return '—'
  return `${fmtNum(v, digits)} %`
}

export function fmtDate(v: string | null | undefined): string {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  return d.toLocaleDateString('ru-RU')
}

export function fmtDateTime(v: string | null | undefined): string {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10)
}

export function defaultRange(days = 30): DateRangeLike {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - days)
  return { date_from: isoDay(from), date_to: isoDay(to) }
}

export interface DateRangeLike {
  date_from: string
  date_to: string
}
