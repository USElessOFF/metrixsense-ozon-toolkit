import { api } from '../api/client'
import { useFetch } from '../api/useFetch'
import type { SellerRatingSection, SellerRatingRow } from '../api/types'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { Card, ErrorState, Loading, PageHead, ScoreBar, Warnings } from '../components/ui'

const columns: Column<SellerRatingRow>[] = [
  { key: 'group_name', title: 'Группа', value: r => r.group_name },
  { key: 'rating_type', title: 'Показатель', value: r => r.rating_type },
  { key: 'score', title: 'Балл', value: r => r.score, render: r => <ScoreBar value={r.score} /> },
  { key: 'description', title: 'Описание', value: r => r.description },
]

export default function Rating() {
  const { data, loading, error, retry } = useFetch(
    () => api.get<SellerRatingSection>('/api/reports/sections/seller-rating'),
    [],
  )

  return (
    <>
      <PageHead title="Рейтинг продавца" sub="Индекс локализации, отзывы, отгрузки и прочие метрики Ozon" />
      {loading && <Loading />}
      {error && <ErrorState message={error} onRetry={retry} />}
      {data && (
        <>
          <Warnings items={data.warnings} />
          <Card>
            <DataTable
              columns={columns}
              rows={data.data}
              rowKey={(r, i) => `${r.rating_type}-${i}`}
              filter={(r, q) => [r.group_name, r.rating_type, r.description].some(v => String(v ?? '').toLowerCase().includes(q))}
              csvName={`seller-rating-${new Date().toISOString().slice(0, 10)}.csv`}
            />
          </Card>
        </>
      )}
    </>
  )
}
