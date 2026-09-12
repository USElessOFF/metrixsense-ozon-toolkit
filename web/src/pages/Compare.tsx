import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { ReportStatus } from '../api/types'
import { Card, ErrorState, Loading, PageHead } from '../components/ui'
import { fmtDateTime, fmtNum } from '../lib/format'

const METRICS: { key: string; betterWhenHigher: boolean; fmt: (v: number) => string }[] = [
  { key: 'Заказано, ₽', betterWhenHigher: true, fmt: v => fmtNum(v, 0) },
  { key: 'Заказано, шт.', betterWhenHigher: true, fmt: v => fmtNum(v, 0) },
  { key: 'Прибыль, ₽', betterWhenHigher: true, fmt: v => fmtNum(v, 0) },
  { key: 'ROMI, %', betterWhenHigher: true, fmt: v => `${fmtNum(v, 1)} %` },
  { key: 'ДРР (оплаченные), %', betterWhenHigher: false, fmt: v => `${fmtNum(v, 1)} %` },
  { key: 'ДРР (всего), %', betterWhenHigher: false, fmt: v => `${fmtNum(v, 1)} %` },
  { key: 'Маржинальность, %', betterWhenHigher: true, fmt: v => `${fmtNum(v, 1)} %` },
]

type Row = Record<string, string | number | null>

function totalsRow(rows: Row[]): Row | null {
  return rows.find(r => String(r['ID Товара']) === 'Всего') ?? null
}

function num(v: unknown): number | null {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export default function Compare() {
  const [reports, setReports] = useState<ReportStatus[]>([])
  const [aId, setAId] = useState('')
  const [bId, setBId] = useState('')
  const [dataA, setDataA] = useState<Row[] | null>(null)
  const [dataB, setDataB] = useState<Row[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const completed = reports.filter(r => r.status === 'completed')

  useEffect(() => {
    api
      .get<ReportStatus[]>('/api/reports/requests?limit=50')
      .then(list => {
        setReports(list)
        const done = list.filter(r => r.status === 'completed')
        if (done[0]) setAId(done[0].request_uuid)
        if (done[1]) setBId(done[1].request_uuid)
      })
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  useEffect(() => {
    if (!aId || !bId) return
    setLoading(true)
    setError(null)
    Promise.all([
      api.get<Row[]>(`/api/reports/requests/${aId}/data`),
      api.get<Row[]>(`/api/reports/requests/${bId}/data`),
    ])
      .then(([a, b]) => {
        setDataA(a)
        setDataB(b)
      })
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [aId, bId])

  const totalA = useMemo(() => (dataA ? totalsRow(dataA) : null), [dataA])
  const totalB = useMemo(() => (dataB ? totalsRow(dataB) : null), [dataB])

  const label = (id: string) => {
    const r = reports.find(x => x.request_uuid === id)
    return r ? `${fmtDateTime(r.created_at)} (${r.date_from?.slice(0, 10)}–${r.date_to?.slice(0, 10)})` : id
  }

  return (
    <>
      <PageHead title="Сравнение отчётов" sub="Итоговые метрики двух готовых отчётов" />
      <Card title="Выбор отчётов">
        <div className="inline-form">
          <label>
            <span className="dim">Отчёт A: </span>
            <select className="input" value={aId} onChange={e => setAId(e.target.value)}>
              {completed.map(r => (
                <option key={r.request_uuid} value={r.request_uuid}>
                  {label(r.request_uuid)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="dim">Отчёт B: </span>
            <select className="input" value={bId} onChange={e => setBId(e.target.value)}>
              {completed.map(r => (
                <option key={r.request_uuid} value={r.request_uuid}>
                  {label(r.request_uuid)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </Card>

      {loading && <Loading />}
      {error && <ErrorState message={error} />}

      {totalA && totalB && (
        <Card title="Итоговые метрики («Всего»)">
          <table className="table">
            <thead>
              <tr>
                <th>Метрика</th>
                <th>A</th>
                <th>B</th>
                <th>Δ</th>
                <th>Лучший</th>
              </tr>
            </thead>
            <tbody>
              {METRICS.filter(m => m.key in totalA && m.key in totalB).map(m => {
                const va = num(totalA[m.key])
                const vb = num(totalB[m.key])
                if (va === null && vb === null) return null
                const best =
                  va === null ? 'B' : vb === null ? 'A' : m.betterWhenHigher ? (va >= vb ? 'A' : 'B') : va <= vb ? 'A' : 'B'
                const delta = va !== null && vb !== null ? vb - va : null
                const maxAbs = Math.max(Math.abs(va ?? 0), Math.abs(vb ?? 0)) || 1
                return (
                  <tr key={m.key}>
                    <td>{m.key}</td>
                    <td>
                      <div className="bar-wrap">
                        <span className="bar" style={{ width: `${va !== null ? Math.min(100, (Math.abs(va) / maxAbs) * 100) : 0}%` }} />
                        <span>{va === null ? '—' : m.fmt(va)}</span>
                      </div>
                    </td>
                    <td>
                      <div className="bar-wrap">
                        <span className="bar bar-b" style={{ width: `${vb !== null ? Math.min(100, (Math.abs(vb) / maxAbs) * 100) : 0}%` }} />
                        <span>{vb === null ? '—' : m.fmt(vb)}</span>
                      </div>
                    </td>
                    <td className={delta === null ? 'dim' : delta < 0 ? 'neg' : 'pos'}>
                      {delta === null ? '—' : (delta > 0 ? '+' : '') + fmtNum(delta, 1)}
                    </td>
                    <td>{best}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}