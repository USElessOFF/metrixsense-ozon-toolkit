import { useState } from 'react'
import { api } from '../api/client'
import { useFetch } from '../api/useFetch'
import type { CashFlowRow, CashFlowSection } from '../api/types'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { PeriodPicker } from '../components/PeriodPicker'
import { Card, ErrorState, Kpi, Loading, PageHead, Warnings } from '../components/ui'
import { defaultRange, fmtDate, fmtMoney } from '../lib/format'

const money = (v: number | null) => (v == null ? '—' : fmtMoney(v))

const columns: Column<CashFlowRow>[] = [
  {
    key: 'date',
    title: 'Период',
    value: r => `${r.date ?? ''} ${r.period_end ?? ''}`,
    render: r => `${fmtDate(r.date)} — ${fmtDate(r.period_end)}`,
  },
  { key: 'orders_amount', title: 'Заказы', align: 'right', value: r => r.orders_amount, render: r => <span className="pos">{money(r.orders_amount)}</span> },
  { key: 'returns_amount', title: 'Возвраты', align: 'right', value: r => r.returns_amount, render: r => <span className="neg">{money(r.returns_amount)}</span> },
  { key: 'commission_amount', title: 'Комиссия', align: 'right', value: r => r.commission_amount, render: r => <span className="neg">{money(r.commission_amount)}</span> },
  { key: 'services_amount', title: 'Услуги', align: 'right', value: r => r.services_amount, render: r => <span className="neg">{money(r.services_amount)}</span> },
  { key: 'delivery_and_return_amount', title: 'Доставка', align: 'right', value: r => r.delivery_and_return_amount, render: r => <span className="neg">{money(r.delivery_and_return_amount)}</span> },
  {
    key: 'total',
    title: 'Итог',
    align: 'right',
    value: r => r.total,
    render: r => (r.total == null ? '—' : <span className={r.total >= 0 ? 'pos' : 'neg'}>{fmtMoney(r.total)}</span>),
  },
]

export default function Cashflow() {
  const [range, setRange] = useState(defaultRange(60))
  const { data, loading, error, retry } = useFetch(
    () => api.post<CashFlowSection>('/api/reports/sections/cashflow', range),
    [range.date_from, range.date_to],
  )

  return (
    <>
      <PageHead
        title="ДДС-журнал"
        sub="Поток денег по неделям (закрытые периоды Ozon)"
        actions={<PeriodPicker from={range.date_from} to={range.date_to} onChange={setRange} />}
      />
      {loading && <Loading />}
      {error && <ErrorState message={error} onRetry={retry} />}
      {data && (
        <>
          <div className="kpi-grid">
            <Kpi label="Заказы" value={fmtMoney(data.total_income)} />
            <Kpi label="Расходы Ozon" value={fmtMoney(data.total_expense)} />
            <Kpi
              label="Чистый поток"
              value={fmtMoney(data.net_flow)}
              hint={data.net_flow >= 0 ? 'в плюсе' : 'в минусе'}
            />
          </div>
          <Warnings items={data.warnings} />
          {Object.keys(data.type_summary).length > 0 && (
            <Card title="Итог по статьям">
              <div className="chips">
                {Object.entries(data.type_summary).map(([type, sum]) => (
                  <span key={type} className={`chip ${sum >= 0 ? 'ok' : 'bad'}`}>
                    {type}: {fmtMoney(sum)}
                  </span>
                ))}
              </div>
            </Card>
          )}
          <Card>
            <DataTable
              columns={columns}
              rows={data.data}
              rowKey={(r, i) => `${r.date}-${i}`}
              filter={(r, q) =>
                [r.date, r.period_end].some(v =>
                  String(v ?? '').toLowerCase().includes(q),
                )
              }
              csvName={`cashflow-${range.date_from}_${range.date_to}.csv`}
            />
          </Card>
        </>
      )}
    </>
  )
}
