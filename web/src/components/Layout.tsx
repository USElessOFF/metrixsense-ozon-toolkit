import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const NAV = [
  { to: '/', label: 'Дашборд', end: true, icon: '◎' },
  { to: '/stocks', label: 'Поставки', icon: '📦' },
  { to: '/prices', label: 'Цены и комиссии', icon: '🏷️' },
  { to: '/cards', label: 'Карточки', icon: '🗃️' },
  { to: '/finance', label: 'Начисления', icon: '🧾' },
  { to: '/cashflow', label: 'ДДС', icon: '💸' },
  { to: '/queries', label: 'Поисковые фразы', icon: '🔍' },
  { to: '/rating', label: 'Рейтинг', icon: '⭐' },
  { to: '/calculator', label: 'Калькулятор', icon: '🧮' },
  { to: '/analogs', label: 'Аналоги', icon: '🧲' },
  { to: '/report', label: 'Отчёты', icon: '📈' },
  { to: '/compare', label: 'Сравнение', icon: '⚖️' },
  { to: '/settings', label: 'Настройки', icon: '⚙️' },
]

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [theme, setTheme] = useState(() => localStorage.getItem('ms-theme') ?? 'dark')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('ms-theme', theme)
  }, [theme])

  const exit = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          Metrix<span>Sense</span>
        </div>
        <nav>
          {NAV.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'active' : undefined)}
            >
              <span aria-hidden>{item.icon}</span> {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">локально · данные не покидают ПК</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <span className="topbar-title">Бесплатная аналитика Ozon</span>
          <div className="topbar-actions">
            <button
              className="btn ghost"
              onClick={() => setTheme(t => (t === 'dark' ? 'light' : 'dark'))}
              title="Сменить тему"
            >
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>
            <span className="user">{user?.username}</span>
            <button className="btn ghost" onClick={exit}>
              Выйти
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
