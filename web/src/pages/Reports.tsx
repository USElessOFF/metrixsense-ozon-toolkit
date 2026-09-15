import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api/client'
import type { ReportStatus } from '../api/types'
import { PeriodPicker } from '../components/PeriodPicker'
import { Badge, Card, PageHead } from '../components/ui'
import { toast } from '../components/Toast'
import { fmtDateTime } from '../lib/format'

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

export default function Reports() {
  const [range, setRange] = useState({ date_from: '', date_to: '' })
  const [report, setReport] = useState<ReportStatus | null>(null)
  const [history, setHistory] = useState<ReportStatus[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  const loadHistory = () => {
    api
      .get<ReportStatus[]>('/api/reports/requests?limit=20')
      .then(list => {
        setHistory(list)
        const active = list.find(r => ACTIVE.has(r.status))
        if (active) setReport(active)
      })
      .catch(() => {})
  }

  useEffect(() => {
    loadHistory()
  }, [])

  useEffect(() => {
    if (!report || !ACTIVE.has(report.status)) return
    timer.current = window.setInterval(async () => {
      try {
        const s = await api.get<ReportStatus>(`/api/reports/requests/${report.request_uuid}`)
        setReport(s)
        loadHistory()
      } catch {
        // следующая попытка
      }
    }, 3000)
    return () => window.clearInterval(timer.current)
  }, [report])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!range.date_from || !range.date_to) return
    setBusy(true)
    setError(null)
    try {
      const created = await api.post<{ request_uuid: string; status: string }>('/api/reports/full', range)
      setReport({
        request_uuid: created.request_uuid,
        status: created.status,
        progress: 0,
        info: null,
        created_at: new Date().toISOString(),
        updated_at: null,
        date_from: range.date_from,
        date_to: range.date_to,
      })
      loadHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось создать отчёт')
    } finally {
      setBusy(false)
    }
  }

  const removeReport = async (uuid: string) => {
    if (!confirm('Удалить отчёт из истории?')) return
    try {
      await api.del(`/api/reports/requests/${uuid}`)
      if (report?.request_uuid === uuid) setReport(null)
      loadHistory()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить отчёт', 'error')
    }
  }

  const [failedDetails, setFailedDetails] = useState<string | null>(null)

  const reportIssueLink = (errText: string) =>
    'https://github.com/USElessOFF/metrixsense-ozon-toolkit/issues/new?title=' +
    encodeURIComponent('Ошибка компиляции отчёта') +
    '&body=' +
    encodeURIComponent(`Ошибка:\n${errText}\n\nВремя: ${new Date().toISOString()}`)

  return (
    <>
      <PageHead title="Отчёты" sub="Сборка в фоне — можно закрыть страницу и вернуться" />
      <Card title="Создание отчёта">
        <form onSubmit={submit} className="inline-form">
          <select className="input" defaultValue="full" aria-label="Тип отчёта">
            <option value="full">Полный отчёт (unit-экономика)</option>
            <option value="performance" disabled>
              Рекламный отчёт — скоро
            </option>
            <option value="stocks" disabled>
              Отчёт по остаткам — скоро
            </option>
          </select>
          <PeriodPicker from={range.date_from} to={range.date_to} onChange={setRange} />
          <button className="btn primary" disabled={busy || !range.date_from || !range.date_to}>
            {busy ? 'Запускаю…' : 'Создать отчёт'}
          </button>
        </form>
        {error && <p className="form-error">{error}</p>}
      </Card>

      {report && (
        <Card title="Статус последнего отчёта">
          <div className="report-status">
            <Badge tone={STATUS_TONE[report.status] ?? 'info'}>
              {STATUS_LABEL[report.status] ?? report.status}
            </Badge>
            <code>{report.request_uuid}</code>
          </div>
          {ACTIVE.has(report.status) && (
            <div className="progress">
              <div className="progress-bar" style={{ width: `${report.progress ?? 0}%` }} />
              <span className="progress-label">{report.progress ?? 0} %</span>
            </div>
          )}
          {report.date_from && report.date_to && (
            <p className="dim">
              Период: {report.date_from.slice(0, 10)} — {report.date_to.slice(0, 10)}
            </p>
          )}
          {report.created_at && <p className="dim">Создан: {fmtDateTime(report.created_at)}</p>}
          {report.info && report.status === 'failed' && (
            <>
              <button
                type="button"
                className="btn ghost tiny"
                onClick={() => setFailedDetails(failedDetails ? null : report.info)}
              >
                {failedDetails ? 'Скрыть ошибку' : 'Показать ошибку'}
              </button>
              {failedDetails && (
                <div className="form-error report-error">
                  <pre>{failedDetails}</pre>
                  <p className="dim">
                    Нашли проблему?{' '}
                    <a href={reportIssueLink(failedDetails)} target="_blank" rel="noreferrer">
                      Напишите issue на GitHub
                    </a>{' '}
                    — приложим этот текст, поможем быстрее.
                  </p>
                </div>
              )}
            </>
          )}
          {report.info && report.status !== 'failed' && <p className="dim">{report.info}</p>}
          {report.status === 'completed' && (
            <p className="report-download">
              <a className="btn primary" href={`/api/reports/requests/${report.request_uuid}/download?fmt=xlsx`}>
                ⬇ Скачать XLSX
              </a>{' '}
              <a className="btn ghost" href={`/api/reports/requests/${report.request_uuid}/download?fmt=csv`}>
                ⬇ CSV
              </a>
            </p>
          )}
        </Card>
      )}

      {history.length > 0 && (
        <Card title="История отчётов">
          <table className="table">
            <thead>
              <tr>
                <th>Создан</th>
                <th>Период</th>
                <th>Статус</th>
                <th>Файл</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {history.map(r => (
                <tr key={r.request_uuid}>
                  <td>{fmtDateTime(r.created_at)}</td>
                  <td>
                    {r.date_from?.slice(0, 10)} — {r.date_to?.slice(0, 10)}
                  </td>
                  <td>
                    <Badge tone={STATUS_TONE[r.status] ?? 'info'}>
                      {STATUS_LABEL[r.status] ?? r.status}
                    </Badge>
                    {r.info && r.status === 'failed' && (
                      <span className="dim" title={r.info}>
                        {' '}
                        ⓘ
                      </span>
                    )}
                  </td>
                  <td>
                    {r.status === 'completed' ? (
                      <>
                        <a className="btn ghost tiny" href={`/api/reports/requests/${r.request_uuid}/download?fmt=xlsx`}>
                          XLSX
                        </a>{' '}
                        <a className="btn ghost tiny" href={`/api/reports/requests/${r.request_uuid}/download?fmt=csv`}>
                          CSV
                        </a>
                      </>
                    ) : r.info && r.status === 'failed' ? (
                      <a
                        className="btn ghost tiny"
                        href={reportIssueLink(r.info)}
                        target="_blank"
                        rel="noreferrer"
                        title={r.info}
                      >
                        ⓘ issue
                      </a>
                    ) : (
                      <span className="dim">—</span>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn danger tiny"
                      onClick={() => removeReport(r.request_uuid)}
                      disabled={r.status === 'in_progress'}
                      title={r.status === 'in_progress' ? 'Дождитесь завершения сборки' : 'Удалить отчёт'}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
