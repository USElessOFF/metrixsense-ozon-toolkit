import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api/client'
import { useFetch } from '../api/useFetch'
import type { AppSettings, OnboardingStatus, Secrets } from '../api/types'
import { Badge, Card, Field, Loading, PageHead } from '../components/ui'
import { toast } from '../components/Toast'

const TAX_LABELS: Record<string, string> = {
  usn_6: 'УСН «Доходы» (6%)',
  usn_15: 'УСН «Доходы − расходы» (15%)',
}

const EMPTY_SECRETS = {
  seller_client_id: '',
  seller_api_key: '',
  performance_client_id: '',
  performance_secret: '',
}

export default function Onboarding() {
  const status = useFetch(() => api.get<OnboardingStatus>('/api/onboarding/status'), [])
  const [secretsForm, setSecretsForm] = useState(EMPTY_SECRETS)
  const [saved, setSaved] = useState<Secrets | null>(null)
  const [settingsForm, setSettingsForm] = useState<AppSettings | null>(null)
  const [conn, setConn] = useState<{ seller: boolean | null; performance: boolean | null } | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    api.get<Secrets>('/api/secrets').then(setSaved).catch(() => {})
    api.get<AppSettings>('/api/settings').then(setSettingsForm).catch(() => {})
  }, [])

  const saveSecrets = async (e: FormEvent) => {
    e.preventDefault()
    setBusy('secrets')
    try {
      const payload = Object.fromEntries(Object.entries(secretsForm).filter(([, v]) => v.trim() !== ''))
      const res = await api.put<Secrets>('/api/secrets', payload)
      setSaved(res)
      setSecretsForm(EMPTY_SECRETS)
      toast('Ключи сохранены')
      status.retry()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить ключи', 'error')
    } finally {
      setBusy(null)
    }
  }

  const checkConnection = async () => {
    setBusy('check')
    try {
      const r = await api.post<{ seller_connected: boolean | null; performance_connected: boolean | null }>(
        '/api/onboarding/check-connection',
        { seller: true, performance: true },
      )
      setConn({ seller: r.seller_connected, performance: r.performance_connected })
      status.retry()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Проверка не удалась', 'error')
    } finally {
      setBusy(null)
    }
  }

  const saveSettings = async (e: FormEvent) => {
    e.preventDefault()
    if (!settingsForm) return
    setBusy('settings')
    try {
      await api.put<AppSettings>('/api/settings', {
        tax_system: settingsForm.tax_system,
        logistics_cost: settingsForm.logistics_cost,
        cost_price_share: settingsForm.cost_price_share,
        ad_budget_percent: settingsForm.ad_budget_percent,
        fbo: settingsForm.fbo,
      })
      toast('Настройки сохранены')
      status.retry()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить настройки', 'error')
    } finally {
      setBusy(null)
    }
  }

  const step = (ok: boolean | undefined, label: string) => (
    <div className="step-row">
      <Badge tone={ok ? 'ok' : 'warn'}>{ok ? '✓' : '•'}</Badge> {label}
    </div>
  )

  return (
    <>
      <PageHead title="Настройка магазина" sub="Ключи Ozon и параметры юнит-экономики — один раз" />
      {status.loading && <Loading />}
      {status.data && (
        <Card title="Готовность">
          <div className="steps-grid">
            {step(status.data.seller_api.configured, 'Seller API ключи сохранены')}
            {step(status.data.performance_api.configured, 'Performance API ключи (опционально)')}
            {step(!status.data.unit_economics_settings.is_default, 'Настройки юнит-экономики заполнены')}
            {step(status.data.ready_for_report, 'Отчёты доступны')}
          </div>
          {status.data.next_steps.length > 0 && (
            <ul className="steps dim">
              {status.data.next_steps.map(s => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <Card title="Ключи Ozon API">
        <form onSubmit={saveSecrets} className="form-grid">
          <Field label="Seller Client ID">
            <input
              className="input"
              value={secretsForm.seller_client_id}
              onChange={e => setSecretsForm(f => ({ ...f, seller_client_id: e.target.value }))}
              placeholder={saved?.seller_client_id ?? 'обязателен для отчётов'}
            />
          </Field>
          <Field label="Seller API Key">
            <input
              className="input"
              type="password"
              value={secretsForm.seller_api_key}
              onChange={e => setSecretsForm(f => ({ ...f, seller_api_key: e.target.value }))}
              placeholder={saved?.seller_api_key ?? '••••'}
            />
          </Field>
          <Field label="Performance Client ID" hint="Рекламный кабинет — можно пропустить">
            <input
              className="input"
              value={secretsForm.performance_client_id}
              onChange={e => setSecretsForm(f => ({ ...f, performance_client_id: e.target.value }))}
              placeholder={saved?.performance_client_id ?? 'опционально'}
            />
          </Field>
          <Field label="Performance Client Secret">
            <input
              className="input"
              type="password"
              value={secretsForm.performance_secret}
              onChange={e => setSecretsForm(f => ({ ...f, performance_secret: e.target.value }))}
              placeholder={saved?.performance_secret ?? 'опционально'}
            />
          </Field>
          <div className="form-actions">
            <button className="btn primary" disabled={busy === 'secrets'}>
              {busy === 'secrets' ? 'Сохраняю…' : 'Сохранить ключи'}
            </button>
            <button type="button" className="btn" onClick={checkConnection} disabled={busy === 'check'}>
              {busy === 'check' ? 'Проверяю…' : 'Проверить подключение'}
            </button>
            {conn && (
              <span className="conn-result">
                Seller: {conn.seller === null ? '—' : conn.seller ? '✓ подключён' : '✗ ошибка'} · Performance:{' '}
                {conn.performance === null ? '—' : conn.performance ? '✓ подключён' : '✗ ошибка'}
              </span>
            )}
          </div>
        </form>
      </Card>

      {settingsForm && (
        <Card title="Юнит-экономика по умолчанию">
          <form onSubmit={saveSettings} className="form-grid">
            <Field label="Налоговая система">
              <select
                className="input"
                value={settingsForm.tax_system}
                onChange={e => setSettingsForm(f => f && { ...f, tax_system: e.target.value })}
              >
                {Object.entries(TAX_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Логистика за заказ, ₽">
              <input
                className="input"
                type="number"
                min="0"
                step="1"
                value={settingsForm.logistics_cost}
                onChange={e => setSettingsForm(f => f && { ...f, logistics_cost: Number(e.target.value) })}
              />
            </Field>
            <Field label="Себестоимость, % от цены" hint="Ozon не отдаёт закупочную цену — оценка">
              <input
                className="input"
                type="number"
                min="1"
                max="100"
                step="1"
                value={Math.round(settingsForm.cost_price_share * 100)}
                onChange={e =>
                  setSettingsForm(f => f && { ...f, cost_price_share: Number(e.target.value) / 100 })
                }
              />
            </Field>
            <Field label="Реклама, % от выручки">
              <input
                className="input"
                type="number"
                min="0"
                max="100"
                step="0.5"
                value={settingsForm.ad_budget_percent}
                onChange={e => setSettingsForm(f => f && { ...f, ad_budget_percent: Number(e.target.value) })}
              />
            </Field>
            <label className="check">
              <input
                type="checkbox"
                checked={settingsForm.fbo}
                onChange={e => setSettingsForm(f => f && { ...f, fbo: e.target.checked })}
              />
              FBO (иначе FBS)
            </label>
            <div className="form-actions">
              <button className="btn primary" disabled={busy === 'settings'}>
                {busy === 'settings' ? 'Сохраняю…' : 'Сохранить настройки'}
              </button>
            </div>
          </form>
        </Card>
      )}
    </>
  )
}
