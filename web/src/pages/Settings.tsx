import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api/client'
import type { AppSettings, Secrets } from '../api/types'
import { Badge, Card, Field, PageHead } from '../components/ui'
import { toast } from '../components/Toast'

const TAX_LABELS: Record<string, string> = {
  usn_6: 'УСН «Доходы» (6%)',
  usn_15: 'УСН «Доходы − расходы» (15%)',
}

export default function Settings() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [secrets, setSecrets] = useState<Secrets | null>(null)
  const [secretsForm, setSecretsForm] = useState({
    seller_client_id: '',
    seller_api_key: '',
    performance_client_id: '',
    performance_secret: '',
  })
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    api.get<AppSettings>('/api/settings').then(setSettings).catch(() => {})
    api.get<Secrets>('/api/secrets').then(setSecrets).catch(() => {})
  }, [])

  const saveSettings = async (e: FormEvent) => {
    e.preventDefault()
    if (!settings) return
    setBusy('settings')
    try {
      const saved = await api.put<AppSettings>('/api/settings', {
        tax_system: settings.tax_system,
        logistics_cost: settings.logistics_cost,
        cost_price_share: settings.cost_price_share,
        ad_budget_percent: settings.ad_budget_percent,
        fbo: settings.fbo,
      })
      setSettings(saved)
      toast('Настройки сохранены')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить настройки', 'error')
    } finally {
      setBusy(null)
    }
  }

  const saveSecrets = async (e: FormEvent) => {
    e.preventDefault()
    setBusy('secrets')
    try {
      const payload = Object.fromEntries(Object.entries(secretsForm).filter(([, v]) => v.trim() !== ''))
      const saved = await api.put<Secrets>('/api/secrets', payload)
      setSecrets(saved)
      setSecretsForm({ seller_client_id: '', seller_api_key: '', performance_client_id: '', performance_secret: '' })
      toast('Ключи сохранены и проверены')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить ключи', 'error')
    } finally {
      setBusy(null)
    }
  }

  const clearSecrets = async () => {
    if (!confirm('Удалить сохранённые ключи Ozon?')) return
    setBusy('clear')
    try {
      await api.del('/api/secrets')
      setSecrets(null)
      toast('Ключи удалены')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить ключи', 'error')
    } finally {
      setBusy(null)
    }
  }

  const validBadge = (valid: boolean) => (
    <Badge tone={valid ? 'ok' : 'warn'}>{valid ? '✓ работает' : 'не проверено'}</Badge>
  )

  return (
    <>
      <PageHead title="Настройки" sub="Параметры расчётов и доступы к Ozon API" />

      {settings && (
        <Card title="Юнит-экономика">
          <form onSubmit={saveSettings} className="form-grid">
            <Field label="Налоговая система">
              <select
                className="input"
                value={settings.tax_system}
                onChange={e => setSettings({ ...settings, tax_system: e.target.value })}
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
                value={settings.logistics_cost}
                onChange={e => setSettings({ ...settings, logistics_cost: Number(e.target.value) })}
              />
            </Field>
            <Field label="Себестоимость, % от цены" hint="Ozon не отдаёт закупочную цену — оценка">
              <input
                className="input"
                type="number"
                min="1"
                max="100"
                step="1"
                value={Math.round(settings.cost_price_share * 100)}
                onChange={e => setSettings({ ...settings, cost_price_share: Number(e.target.value) / 100 })}
              />
            </Field>
            <Field label="Реклама, % от выручки">
              <input
                className="input"
                type="number"
                min="0"
                max="100"
                step="0.5"
                value={settings.ad_budget_percent}
                onChange={e => setSettings({ ...settings, ad_budget_percent: Number(e.target.value) })}
              />
            </Field>
            <label className="check">
              <input
                type="checkbox"
                checked={settings.fbo}
                onChange={e => setSettings({ ...settings, fbo: e.target.checked })}
              />
              FBO (иначе FBS)
            </label>
            <div className="form-actions">
              <button className="btn primary" disabled={busy === 'settings'}>
                {busy === 'settings' ? 'Сохраняю…' : 'Сохранить'}
              </button>
            </div>
          </form>
        </Card>
      )}

      <Card title="Ключи Ozon API">
        {secrets && (
          <div className="secrets-current">
            <p>Seller Client ID: <code>{secrets.seller_client_id ?? '—'}</code> {validBadge(secrets.seller_valid)}</p>
            <p>Performance: <code>{secrets.performance_client_id ?? '—'}</code> {validBadge(secrets.performance_valid)}</p>
          </div>
        )}
        <form onSubmit={saveSecrets} className="form-grid">
          <Field label="Seller Client ID">
            <input
              className="input"
              value={secretsForm.seller_client_id}
              onChange={e => setSecretsForm(f => ({ ...f, seller_client_id: e.target.value }))}
              placeholder="положительное целое число из кабинета Ozon"
            />
          </Field>
          <Field label="Seller API Key">
            <input
              className="input"
              type="password"
              value={secretsForm.seller_api_key}
              onChange={e => setSecretsForm(f => ({ ...f, seller_api_key: e.target.value }))}
              placeholder="Api-Key из кабинета Ozon"
            />
          </Field>
          <Field label="Performance Client ID" hint="опционально — рекламный кабинет">
            <input
              className="input"
              value={secretsForm.performance_client_id}
              onChange={e => setSecretsForm(f => ({ ...f, performance_client_id: e.target.value }))}
              placeholder="опционально"
            />
          </Field>
          <Field label="Performance Client Secret">
            <input
              className="input"
              type="password"
              value={secretsForm.performance_secret}
              onChange={e => setSecretsForm(f => ({ ...f, performance_secret: e.target.value }))}
              placeholder="опционально"
            />
          </Field>
          <div className="form-actions">
            <button className="btn primary" disabled={busy === 'secrets'}>
              {busy === 'secrets' ? 'Сохраняю…' : 'Сохранить и проверить'}
            </button>
            {secrets && (
              <button type="button" className="btn danger" onClick={clearSecrets} disabled={busy === 'clear'}>
                Удалить ключи
              </button>
            )}
          </div>
        </form>
        <p className="hint">Ключи шифруются перед записью на диск и в ответах API маскируются.</p>
      </Card>
    </>
  )
}
