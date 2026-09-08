import { useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api/client'
import type { CalculatorResult } from '../api/types'
import { Badge, Card, Field, PageHead, Warnings } from '../components/ui'
import { fmtMoney, fmtPercent } from '../lib/format'

const SOURCE_TONE: Record<string, string> = {
  api: 'ok',
  manual: 'info',
  settings: 'warn',
}

export default function Calculator() {
  const [mode, setMode] = useState<'manual' | 'existing'>('manual')
  const [sku, setSku] = useState('')
  const [purchasePrice, setPurchasePrice] = useState('500')
  const [salePrice, setSalePrice] = useState('')
  const [commission, setCommission] = useState('')
  const [logistics, setLogistics] = useState('')
  const [acquiring, setAcquiring] = useState('')
  const [adBudget, setAdBudget] = useState('')
  const [result, setResult] = useState<CalculatorResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const numOrNull = (v: string) => (v.trim() === '' ? null : Number(v))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.post<CalculatorResult>('/api/calculator', {
        mode,
        sku: mode === 'existing' ? Number(sku) : null,
        purchase_price: Number(purchasePrice),
        sale_price: numOrNull(salePrice),
        commission_percent: numOrNull(commission),
        logistics_cost: numOrNull(logistics),
        acquiring_percent: numOrNull(acquiring),
        ad_budget_percent: numOrNull(adBudget),
      })
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Расчёт не удался')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHead title="Калькулятор юнит-экономики" sub="Прибыль с единицы товара до закупки" />
      <div className="calc-layout">
        <Card title="Параметры">
          <form onSubmit={submit} className="form-grid">
            <div className="seg">
              <button type="button" className={mode === 'manual' ? 'active' : ''} onClick={() => setMode('manual')}>
                Новинка (вручную)
              </button>
              <button type="button" className={mode === 'existing' ? 'active' : ''} onClick={() => setMode('existing')}>
                Товар с Ozon
              </button>
            </div>
            {mode === 'existing' && (
              <Field label="SKU товара">
                <input className="input" value={sku} onChange={e => setSku(e.target.value)} required placeholder="например 123456789" />
              </Field>
            )}
            <Field label="Закупочная цена, ₽">
              <input className="input" type="number" min="1" step="0.01" value={purchasePrice} onChange={e => setPurchasePrice(e.target.value)} required />
            </Field>
            <Field label="Цена продажи, ₽" hint={mode === 'existing' ? 'пусто — взять из API' : undefined}>
              <input className="input" type="number" min="1" step="0.01" value={salePrice} onChange={e => setSalePrice(e.target.value)} />
            </Field>
            {mode === 'manual' && (
              <Field label="Комиссия Ozon, %">
                <input className="input" type="number" min="0" max="100" step="0.5" value={commission} onChange={e => setCommission(e.target.value)} />
              </Field>
            )}
            <Field label="Логистика, ₽" hint={mode === 'existing' ? 'пусто — из API' : undefined}>
              <input className="input" type="number" min="0" step="1" value={logistics} onChange={e => setLogistics(e.target.value)} />
            </Field>
            {mode === 'manual' && (
              <Field label="Эквайринг, %">
                <input className="input" type="number" min="0" max="100" step="0.1" value={acquiring} onChange={e => setAcquiring(e.target.value)} />
              </Field>
            )}
            <Field label="Реклама, % от выручки" hint="пусто — взять настройку магазина">
              <input className="input" type="number" min="0" step="0.5" value={adBudget} onChange={e => setAdBudget(e.target.value)} />
            </Field>
            <button className="btn primary" disabled={busy}>
              {busy ? 'Считаю…' : 'Рассчитать'}
            </button>
            {error && <p className="form-error">{error}</p>}
          </form>
        </Card>

        {result && (
          <div>
            <Card title="Результат">
              <div className="kpi-grid">
                <div className="kpi">
                  <span className="kpi-label">Прибыль / шт</span>
                  <span className={`kpi-value ${result.profit >= 0 ? 'pos' : 'neg'}`}>{fmtMoney(result.profit)}</span>
                </div>
                <div className="kpi">
                  <span className="kpi-label">Маржа</span>
                  <span className="kpi-value">{fmtPercent(result.margin_percent)}</span>
                </div>
                <div className="kpi">
                  <span className="kpi-label">Наценка</span>
                  <span className="kpi-value">{fmtPercent(result.markup_percent)}</span>
                </div>
              </div>
              <div className="result-lines">
                <div className="result-line">
                  <span>Выручка за единицу</span>
                  <b>{fmtMoney(result.revenue)}</b>
                </div>
                {result.cost_lines.map(l => (
                  <div key={l.name} className="result-line">
                    <span>
                      {l.name} <Badge tone={SOURCE_TONE[l.source] ?? 'info'}>{l.source}</Badge>
                    </span>
                    <b>−{fmtMoney(l.amount)}</b>
                  </div>
                ))}
                <div className="result-line total">
                  <span>Расходы всего</span>
                  <b>−{fmtMoney(result.total_costs)}</b>
                </div>
                <div className="result-line">
                  <span>
                    Налог · {result.tax_system} <Badge tone="warn">{result.tax_system}</Badge>
                  </span>
                  <b>−{fmtMoney(result.tax)}</b>
                </div>
                <div className="result-line grand">
                  <span>Чистая прибыль</span>
                  <b>{fmtMoney(result.profit)}</b>
                </div>
              </div>
            </Card>
            {result.warnings.length > 0 && <Warnings items={result.warnings} />}
          </div>
        )}
      </div>
    </>
  )
}
