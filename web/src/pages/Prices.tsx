import { api } from '../api/client'
import { useFetch } from '../api/useFetch'
import type { PricesCommissionsRow, PricesCommissionsSection } from '../api/types'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { Card, ErrorState, Loading, PageHead, Warnings } from '../components/ui'
import { fmtMoney, fmtNum, fmtPercent } from '../lib/format'

const columns: Column<PricesCommissionsRow>[] = [
  { key: 'offer_id', title: 'Артикул', value: r => r.offer_id },
  { key: 'product_id', title: 'Product ID', value: r => r.product_id },
  { key: 'price', title: 'Цена', align: 'right', value: r => r.price, render: r => fmtMoney(r.price) },
  { key: 'old_price', title: 'До скидки', align: 'right', value: r => r.old_price, render: r => fmtMoney(r.old_price) },
  { key: 'min_price', title: 'Мин.', align: 'right', value: r => r.min_price, render: r => fmtMoney(r.min_price) },
  { key: 'marketing_price', title: 'С акцией', align: 'right', value: r => r.marketing_price, render: r => fmtMoney(r.marketing_price) },
  { key: 'commission_fbo_percent', title: 'Комиссия FBO', align: 'right', value: r => r.commission_fbo_percent, render: r => fmtPercent(r.commission_fbo_percent) },
  { key: 'commission_fbs_percent', title: 'Комиссия FBS', align: 'right', value: r => r.commission_fbs_percent, render: r => fmtPercent(r.commission_fbs_percent) },
  { key: 'acquiring_percent', title: 'Эквайринг', align: 'right', value: r => r.acquiring_percent, render: r => fmtPercent(r.acquiring_percent) },
  { key: 'logistics_fbo_range', title: 'Логистика FBO', value: r => r.logistics_fbo_range },
  { key: 'delivery_fbo', title: 'Доставка FBO', align: 'right', value: r => r.delivery_fbo, render: r => fmtMoney(r.delivery_fbo) },
  { key: 'return_flow_fbo', title: 'Возвратный поток', align: 'right', value: r => r.return_flow_fbo, render: r => fmtMoney(r.return_flow_fbo) },
  { key: 'volume_weight_l', title: 'Объёмный вес, л', align: 'right', value: r => r.volume_weight_l, render: r => fmtNum(r.volume_weight_l) },
]

export default function Prices() {
  const { data, loading, error, retry } = useFetch(
    () => api.get<PricesCommissionsSection>('/api/reports/sections/prices-commissions'),
    [],
  )

  return (
    <>
      <PageHead title="Цены и комиссии" sub="Актуальные цены, комиссии и логистика по каждому товару" />
      {loading && <Loading />}
      {error && <ErrorState message={error} onRetry={retry} />}
      {data && (
        <>
          <Warnings items={data.warnings} />
          <Card>
            <DataTable
              columns={columns}
              rows={data.data}
              rowKey={r => r.offer_id ?? r.product_id ?? Math.random()}
              filter={(r, q) => [r.offer_id, r.product_id].some(v => String(v ?? '').toLowerCase().includes(q))}
              csvName={`prices-commissions-${new Date().toISOString().slice(0, 10)}.csv`}
            />
          </Card>
        </>
      )}
    </>
  )
}
