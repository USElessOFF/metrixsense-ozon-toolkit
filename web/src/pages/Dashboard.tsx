import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useFetch } from '../api/useFetch'
import type { OnboardingStatus, TopActionsSection } from '../api/types'
import { Badge, Card, ErrorState, Loading, PageHead, Warnings } from '../components/ui'

const PRIORITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }

const ACTION_LINK: Record<string, string> = {
  restock: '/stocks',
  dead_stock: '/stocks',
  high_costs: '/finance',
  search_no_sales: '/queries',
}

export default function Dashboard() {
  const actions = useFetch(() => api.post<TopActionsSection>('/api/reports/top-actions'), [])
  const onboarding = useFetch(() => api.get<OnboardingStatus>('/api/onboarding/status'), [])

  const list = [...(actions.data?.actions ?? [])].sort(
    (a, b) => (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9),
  )

  return (
    <>
      <PageHead title="Дашборд" sub="Что требует внимания прямо сейчас" />
      {onboarding.data && !onboarding.data.ready_for_report && (
        <Card title="Первичная настройка не завершена" className="onboard-hint">
          <ul className="steps">
            {onboarding.data.next_steps.map(s => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <Link className="btn primary" to="/onboarding">
            Пройти настройку
          </Link>
        </Card>
      )}
      {actions.loading && <Loading />}
      {actions.error && <ErrorState message={actions.error} onRetry={actions.retry} />}
      {actions.data && (
        <>
          <Warnings items={actions.data.warnings} />
          {list.length === 0 ? (
            <Card>
              <p className="state">Действий не найдено — магазин в порядке 👌</p>
            </Card>
          ) : (
            <div className="action-grid">
              {list.map(a => (
                <Card key={a.action_type} className={`action act-${a.priority}`}>
                  <div className="action-top">
                    <Badge tone={a.priority}>{a.priority}</Badge>
                    <span className="action-count">{a.sku_count} SKU</span>
                  </div>
                  <h3>{a.title}</h3>
                  <p>{a.impact}</p>
                  <div className="action-foot">
                    <span className="dim">
                      {a.skus.slice(0, 8).join(', ')}
                      {a.skus.length > 8 ? '…' : ''}
                    </span>
                    {ACTION_LINK[a.action_type] && (
                      <Link className="btn ghost tiny" to={ACTION_LINK[a.action_type]}>
                        Разобрать
                      </Link>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </>
  )
}
