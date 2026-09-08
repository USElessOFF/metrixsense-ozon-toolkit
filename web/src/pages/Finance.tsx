import { useState } from 'react'
import { api } from '../api/client'
import { useFetch } from '../api/useFetch'
import type { FinanceExpensesSection, FinanceExpenseRow } from '../api/types'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { PeriodPicker } from '../components/PeriodPicker'
import { Card, ErrorState, Kpi, Loading, PageHead, Warnings } from '../components/ui'
import { defaultRange, fmtMoney } from '../lib/format'


const columns: Column<FinanceExpenseRow>[] = [
  { key: 'sku', title: 'SKU', value: r => r.sku },
  { key: 'accruals_for_sale', title: 'Начислено за продажи', align: 'right', value: r => r.accruals_for_sale, render: r => fmtMoney(r.accruals_for_sale) },
  { key: 'sale_commission', title: 'Комиссия', align: 'right', value: r => r.sale_commission, render: r => fmtMoney(r.sale_commission) },
  { key: 'delivery', title: 'Доставка', align: 'right', value: r => r.delivery, render: r => fmtMoney(r.delivery) },
  { key: 'return_delivery', title: 'Возвратная доставка', align: 'right', value: r => r.return_delivery, render: r => fmtMoney(r.return_delivery) },
  { key: 'services', title: 'Услуги Ozon', align: 'right', value: r => r.services, render: r => fmtMoney(r.services) },
  { key: 'actual_logistics_per_unit', title: 'Логистика/шт (факт)', align: 'right', value: r => r.actual_logistics_per_unit, render: r => fmtMoney(r.actual_logistics_per_unit) },
]

export default function Finance() {
  const [range, setRange] = useState(defaultRange())
  const { data, loading, error, retry } = useFetch(
    () => api.post<FinanceExpensesSection>('/api/reports/sections/finance-expenses', range),
    [range.date_from, range.date_to],
  )

  const numericTotals = Object.entries(data?.totals ?? {}).filter(
    ([, v]) => typeof v === 'number',
  ) as [string, number][]

  return (
    <>
      <PageHead
        title="Финансовые начисления"
        sub="Фактические комиссии, логистика и услуги за период"
        actions={<PeriodPicker from={range.date_from} to={range.date_to} onChange={setRange} />}
      />
      {loading && <Loading />}
      {error && <ErrorState message={error} onRetry={retry} />}
      {data && (
        <>
          {numericTotals.length > 0 && (
            <div className="kpi-grid">
              {numericTotals.slice(0, 4).map(([k, v]) => (
                <Kpi key={k} label={k} value={fmtMoney(v)} />
              ))}
            </div>
          )}
          <Warnings items={data.warnings} />
          <Card>
            <DataTable
              columns={columns}
              rows={data.data}
              rowKey={r => r.sku ?? Math.random()}
              filter={(r, q) => String(r.sku ?? '').includes(q)}
              csvName={`finance-${range.date_from}_${range.date_to}.csv`}
              emptyText="Операций за период нет — попробуйте расширить диапазон"
            />
          </Card>
        </>
      )}
    </>
  )
}
