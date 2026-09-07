import { api } from '../api/client'
import { useFetch } from '../api/useFetch'
import type { StockPlanningSection, StockPlanningRow } from '../api/types'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { Badge, Card, ErrorState, Kpi, Loading, PageHead, Warnings } from '../components/ui'
import { fmtDate, fmtInt, fmtNum } from '../lib/format'

const PRIORITY_TONE: Record<string, string> = {
  critical: 'critical',
  low: 'warn',
  normal: 'ok',
  'no-velocity': 'info',
}

const columns: Column<StockPlanningRow>[] = [
  { key: 'sku', title: 'SKU', value: r => r.sku },
  { key: 'name', title: 'Товар', value: r => r.name },
  { key: 'offer_id', title: 'Артикул', value: r => r.offer_id },
  { key: 'current_stock', title: 'Остаток', align: 'right', value: r => r.current_stock, render: r => fmtInt(r.current_stock) },
  { key: 'ads', title: 'ADS, шт/день', align: 'right', value: r => r.ads, render: r => fmtNum(r.ads) },
  { key: 'days_of_stock', title: 'Дней запаса', align: 'right', value: r => r.days_of_stock, render: r => fmtNum(r.days_of_stock, 1) },
  { key: 'idc', title: 'IDC Ozon', align: 'right', value: r => r.idc, render: r => fmtNum(r.idc, 1) },
  { key: 'recommended_units', title: 'К поставке', align: 'right', value: r => r.recommended_units, render: r => fmtInt(r.recommended_units) },
  { key: 'priority', title: 'Приоритет', value: r => r.priority, render: r => <Badge tone={PRIORITY_TONE[r.priority] ?? 'info'}>{r.priority}</Badge> },
  { key: 'due_by', title: 'Останется ноль', value: r => r.due_by, render: r => fmtDate(r.due_by) },
]

export default function Stocks() {
  const { data, loading, error, retry } = useFetch(
    () => api.get<StockPlanningSection>('/api/reports/sections/stocks'),
    [],
  )

  const s = data?.plan_summary

  return (
    <>
      <PageHead
        title="Планирование поставок"
        sub={data ? `Целевой запас ${data.target_days} дн · критический порог ${data.critical_days} дн` : undefined}
      />
      {loading && <Loading />}
      {error && <ErrorState message={error} onRetry={retry} />}
      {data && (
        <>
          <div className="kpi-grid">
            <Kpi label="SKU в плане" value={fmtInt(s?.skus_total)} />
            <Kpi label="Нужна поставка" value={fmtInt(s?.skus_needs_reorder)} />
            <Kpi label="Критический запас" value={fmtInt(s?.skus_critical)} />
            <Kpi label="К отгрузке, шт" value={fmtInt(s?.total_units_to_ship)} />
          </div>
          <Warnings items={data.warnings} />
          <Card>
            <DataTable
              columns={columns}
              rows={data.data}
              rowKey={r => r.sku ?? r.offer_id ?? Math.random()}
              filter={(r, q) =>
                [r.name, r.offer_id, r.sku].some(v => String(v ?? '').toLowerCase().includes(q))
              }
              csvName={`stocks-${new Date().toISOString().slice(0, 10)}.csv`}
              expanded={r =>
                r.warehouses.length === 0 ? (
                  <span className="dim">Нет разбивки по складам</span>
                ) : (
                  <table className="inner-table">
                    <thead>
                      <tr>
                        <th>Склад</th>
                        <th className="num">Доступно</th>
                        <th className="num">Зарезервировано</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.warehouses.map((w, i) => (
                        <tr key={i}>
                          <td>{w.name ?? '—'}</td>
                          <td className="num">{fmtInt(w.present)}</td>
                          <td className="num">{fmtInt(w.reserved)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
              }
            />
          </Card>
        </>
      )}
    </>
  )
}
