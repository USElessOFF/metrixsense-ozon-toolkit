import { useState } from 'react'
import { api } from '../api/client'
import { useFetch } from '../api/useFetch'
import type { SearchQueriesSection, SearchQueryRow } from '../api/types'
import { DataTable } from '../components/DataTable'
import type { Column } from '../components/DataTable'
import { PeriodPicker } from '../components/PeriodPicker'
import { Card, ErrorState, Loading, PageHead, Warnings } from '../components/ui'
import { defaultRange, fmtInt, fmtMoney, fmtNum, fmtPercent } from '../lib/format'

const columns: Column<SearchQueryRow>[] = [
  { key: 'phrase', title: 'Фраза', value: r => r.phrase },
  { key: 'category', title: 'Категория', value: r => r.category },
  { key: 'sku', title: 'SKU', value: r => r.sku },
  { key: 'gmv', title: 'GMV', align: 'right', value: r => r.gmv, render: r => fmtMoney(r.gmv) },
  { key: 'position', title: 'Позиция', align: 'right', value: r => r.position, render: r => fmtNum(r.position, 1) },
  { key: 'unique_search_users', title: 'Искали, чел', align: 'right', value: r => r.unique_search_users, render: r => fmtInt(r.unique_search_users) },
  { key: 'unique_view_users', title: 'Смотрели, чел', align: 'right', value: r => r.unique_view_users, render: r => fmtInt(r.unique_view_users) },
  { key: 'view_conversion', title: 'Конверсия', align: 'right', value: r => r.view_conversion, render: r => fmtPercent(r.view_conversion) },
]

export default function SearchQueries() {
  const [range, setRange] = useState(defaultRange())
  const { data, loading, error, retry } = useFetch(
    () => api.post<SearchQueriesSection>('/api/reports/sections/search-queries', range),
    [range.date_from, range.date_to],
  )

  return (
    <>
      <PageHead
        title="Поисковые фразы"
        sub="По каким запросам вас находят: показы, позиции, конверсия"
        actions={<PeriodPicker from={range.date_from} to={range.date_to} onChange={setRange} />}
      />
      {loading && <Loading />}
      {error && <ErrorState message={error} onRetry={retry} />}
      {data && (
        <>
          <Warnings items={data.warnings} />
          <Card>
            <DataTable
              columns={columns}
              rows={data.data}
              rowKey={(r, i) => `${r.phrase}-${r.sku}-${i}`}
              filter={(r, q) => [r.phrase, r.category, r.sku, r.offer_id].some(v => String(v ?? '').toLowerCase().includes(q))}
              csvName={`search-queries-${range.date_from}_${range.date_to}.csv`}
            />
          </Card>
        </>
      )}
    </>
  )
}
