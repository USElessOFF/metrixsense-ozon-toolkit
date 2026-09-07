import { api } from '../api/client'
import { useFetch } from '../api/useFetch'
import type { ProductCardRow, ProductCardsSection } from '../api/types'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { Badge, Card, ErrorState, Loading, PageHead, Warnings } from '../components/ui'
import { fmtInt, fmtMoney, fmtNum } from '../lib/format'

const dims = (r: ProductCardRow) =>
  [r.local_length_mm, r.local_width_mm, r.local_height_mm].every(v => v !== null)
    ? `${r.local_length_mm}×${r.local_width_mm}×${r.local_height_mm}`
    : '—'

const columns: Column<ProductCardRow>[] = [
  { key: 'sku', title: 'SKU', value: r => r.sku },
  { key: 'name', title: 'Товар', value: r => r.name },
  { key: 'offer_id', title: 'Артикул', value: r => r.offer_id },
  { key: 'price', title: 'Цена', align: 'right', value: r => r.price, render: r => fmtMoney(r.price) },
  { key: 'old_price', title: 'Старая', align: 'right', value: r => r.old_price, render: r => fmtMoney(r.old_price) },
  { key: 'min_price', title: 'Мин.', align: 'right', value: r => r.min_price, render: r => fmtMoney(r.min_price) },
  { key: 'commission_fbo_percent', title: 'Комиссия FBO', align: 'right', value: r => r.commission_fbo_percent, render: r => fmtNum(r.commission_fbo_percent, 1) },
  { key: 'delivery_fbo', title: 'Доставка FBO', align: 'right', value: r => r.delivery_fbo, render: r => fmtMoney(r.delivery_fbo) },
  { key: 'return_fbo', title: 'Возврат FBO', align: 'right', value: r => r.return_fbo, render: r => fmtMoney(r.return_fbo) },
  { key: 'volume_weight_l', title: 'Объёмный вес, л', align: 'right', value: r => r.volume_weight_l, render: r => fmtNum(r.volume_weight_l) },
  { key: 'dims', title: 'Габариты, мм', value: r => r.local_length_mm, render: dims },
  { key: 'local_weight_g', title: 'Вес, г', align: 'right', value: r => r.local_weight_g, render: r => fmtInt(r.local_weight_g) },
  { key: 'local_volume_l', title: 'Объём, л', align: 'right', value: r => r.local_volume_l, render: r => fmtNum(r.local_volume_l) },
  { key: 'oversize', title: 'КГТ', value: r => (r.oversize ? 'да' : 'нет'), render: r => (r.oversize === null ? <span>—</span> : r.oversize ? <Badge tone="warn">КГТ</Badge> : <Badge tone="ok">нет</Badge>) },
]

export default function ProductCards() {
  const { data, loading, error, retry } = useFetch(
    () => api.post<ProductCardsSection>('/api/reports/sections/product-cards', {}),
    [],
  )

  return (
    <>
      <PageHead title="Карточки товаров" sub="Габариты, объёмный вес и тарифные параметры" />
      {loading && <Loading />}
      {error && <ErrorState message={error} onRetry={retry} />}
      {data && (
        <>
          <Warnings items={data.warnings} />
          <Card>
            <DataTable
              columns={columns}
              rows={data.data}
              rowKey={r => r.sku ?? r.offer_id ?? Math.random()}
              filter={(r, q) => [r.name, r.offer_id, r.sku].some(v => String(v ?? '').toLowerCase().includes(q))}
              csvName={`product-cards-${new Date().toISOString().slice(0, 10)}.csv`}
            />
          </Card>
        </>
      )}
    </>
  )
}
