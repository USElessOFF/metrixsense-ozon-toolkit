import { useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api/client'
import type { AnalogsResponse } from '../api/types'
import { Card, Empty, ErrorState, Field, Loading, PageHead, ScoreBar } from '../components/ui'
import { downloadCsv } from '../lib/csv'
import { fmtMoney } from '../lib/format'

export default function Analogs() {
  const [sku, setSku] = useState('')
  const [top, setTop] = useState('10')
  const [minSimilarity, setMinSimilarity] = useState('0.1')
  const [result, setResult] = useState<AnalogsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setSearched(false)
    try {
      const params = new URLSearchParams({
        sku,
        top,
        min_similarity: minSimilarity,
      })
      const res = await api.get<AnalogsResponse>(`/api/analogs?${params}`)
      setResult(res)
      setSearched(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Поиск не удался')
    } finally {
      setLoading(false)
    }
  }

  const exportCsv = () => {
    if (!result) return
    downloadCsv(
      `analogs-${result.sku}.csv`,
      ['SKU', 'Название', 'Артикул', 'Близость', 'Цена'],
      result.analogs.map(a => [a.sku, a.name, a.offer_id, a.similarity, a.price]),
    )
  }

  return (
    <>
      <PageHead title="Поиск аналогов" sub="Похожие товары каталога по TF-IDF близости названий" />
      <Card>
        <form onSubmit={submit} className="inline-form">
          <Field label="SKU товара">
            <input className="input" value={sku} onChange={e => setSku(e.target.value)} required placeholder="SKU с карточки" />
          </Field>
          <Field label="Сколько показать">
            <input className="input" type="number" min="1" max="50" value={top} onChange={e => setTop(e.target.value)} />
          </Field>
          <Field label="Мин. близость">
            <input className="input" type="number" min="0" max="1" step="0.05" value={minSimilarity} onChange={e => setMinSimilarity(e.target.value)} />
          </Field>
          <button className="btn primary" disabled={loading || !sku}>
            {loading ? 'Ищу…' : 'Найти'}
          </button>
        </form>
        {error && <ErrorState message={error} />}
      </Card>

      {loading && <Loading text="Ищу аналоги в каталоге…" />}
      {result && !loading && (
        <Card
          title={result.name ?? `SKU ${result.sku}`}
          actions={
            <button className="btn ghost tiny" onClick={exportCsv}>
              CSV
            </button>
          }
        >
          <p className="dim">Каталог поиска: {result.total_catalog} товаров</p>
          {result.analogs.length === 0 ? (
            searched ? <Empty text="Аналогов не нашлось — попробуйте снизить мин. близость" /> : null
          ) : (
            <div className="analog-list">
              {result.analogs.map(a => (
                <div key={a.sku} className="analog">
                  <div className="analog-main">
                    <b>{a.name}</b>
                    <span className="dim">SKU {a.sku}{a.offer_id ? ` · ${a.offer_id}` : ''}</span>
                  </div>
                  <ScoreBar value={a.similarity} max={1} />
                  <span className="analog-price">{a.price === null ? '—' : fmtMoney(a.price)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </>
  )
}
