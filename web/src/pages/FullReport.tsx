import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api/client'
import type { ReportStatus } from '../api/types'
import { PeriodPicker } from '../components/PeriodPicker'
import { Badge, Card, PageHead } from '../components/ui'
import { defaultRange, fmtDateTime } from '../lib/format'

const STATUS_TONE: Record<string, string> = {
  pending: 'info',
  in_progress: 'warn',
  completed: 'ok',
  failed: 'error',
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'в очереди',
  in_progress: 'собирается',
  completed: 'готов',
  failed: 'ошибка',
}

const ACTIVE = new Set(['pending', 'in_progress'])

export default function FullReport() {
  const [range, setRange] = useState(defaultRange())
  const [report, setReport] = useState<ReportStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!report || !ACTIVE.has(report.status)) return
    timer.current = window.setInterval(async () => {
      try {
        const s = await api.get<ReportStatus>(`/api/reports/requests/${report.request_uuid}`)
        setReport(s)
      } catch {
        // следующая попытка
      }
    }, 3000)
    return () => window.clearInterval(timer.current)
  }, [report])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const created = await api.post<{ request_uuid: string; status: string }>('/api/reports/full', range)
      setReport({ request_uuid: created.request_uuid, status: created.status, info: null, created_at: null, updated_at: null })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось создать отчёт')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHead title="Полный отчёт" sub="Собирается в фоне — можно закрыть страницу и вернуться" />
      <Card>
        <form onSubmit={submit} className="inline-form">
          <PeriodPicker from={range.date_from} to={range.date_to} onChange={setRange} />
          <button className="btn primary" disabled={busy}>
            {busy ? 'Запускаю…' : 'Создать отчёт'}
          </button>
        </form>
        {error && <p className="form-error">{error}</p>}
      </Card>

      {report && (
        <Card title="Статус">
          <div className="report-status">
            <Badge tone={STATUS_TONE[report.status] ?? 'info'}>
              {STATUS_LABEL[report.status] ?? report.status}
            </Badge>
            <code>{report.request_uuid}</code>
          </div>
          {report.created_at && <p className="dim">Создан: {fmtDateTime(report.created_at)}</p>}
          {report.updated_at && <p className="dim">Обновлён: {fmtDateTime(report.updated_at)}</p>}
          {report.info && <p className={report.status === 'failed' ? 'form-error' : 'dim'}>{report.info}</p>}
          {report.status === 'completed' && (
            <p className="dim">Файл отчёта лежит в <code>backend/files/</code> — Excel готов к скачиванию.</p>
          )}
        </Card>
      )}
    </>
  )
}
