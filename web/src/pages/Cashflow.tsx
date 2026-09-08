import { useState } from 'react'
import { api } from '../api/client'
import { useFetch } from '../api/useFetch'
import type { CashFlowRow, CashFlowSection } from '../api/types'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { PeriodPicker } from '../components/PeriodPicker'
import { Card, ErrorState, Kpi, Loading, PageHead, Warnings } from '../components/ui'
import { defaultRange, fmtDate, fmtMoney } from '../lib/format'

const columns: Column<CashFlowRow>[] = [
  { key: 'date', title: 'Дата', value: r => r.date, render: r => fmtDate(r.date) },
  { key: 'operation_type_name', title: 'Операция', value: r => r.operation_type_name },
  {
    key: 'amount',
    title: 'Сумма',
    align: 'right',
    value: r => r.amount,
    render: r =>
      r.amount === null ? (
        '—'
      ) : (
        <span className={r.amount >= 0 ? 'pos' : 'neg'}>{fmtMoney(r.amount)}</span>
      ),
  },
  { key: 'balance_after', title: 'Баланс после', align: 'right', value: r => r.balance_after, render: r => fmtMoney(r.balance_after) },
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
        sub="Все операции периода с накопленным балансом"
        actions={<PeriodPicker from={range.date_from} to={range.date_to} onChange={setRange} />}
      />
      {loading && <Loading />}
      {error && <ErrorState message={error} onRetry={retry} />}
      {data && (
        <>
          <div className="kpi-grid">
            <Kpi label="Приход" value={fmtMoney(data.total_income)} />
            <Kpi label="Расход" value={fmtMoney(data.total_expense)} />
            <Kpi
              label="Чистый поток"
              value={fmtMoney(data.net_flow)}
              hint={data.net_flow >= 0 ? 'в плюсе' : 'в минусе'}
            />
          </div>
          <Warnings items={data.warnings} />
          {Object.keys(data.type_summary).length > 0 && (
            <Card title="Итог по типам операций">
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
              rowKey={(r, i) => `${r.date}-${r.operation_type}-${i}`}
              filter={(r, q) =>
                [r.operation_type_name, r.operation_type, r.date].some(v =>
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
