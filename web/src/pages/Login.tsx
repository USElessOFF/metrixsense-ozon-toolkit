import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function Login() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('metrixsense')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'login') await login(username, password)
      else await register(username, password)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Что-то пошло не так')
    } finally {
      setBusy(false)
    }
  }

  const switchMode = () => {
    setMode(m => (m === 'login' ? 'register' : 'login'))
    setError(null)
  }

  return (
    <div className="auth-screen">
      <main className="auth-card">
        <div className="logo">
          Metrix<span>Sense</span>
        </div>
        <p className="tagline">Бесплатная аналитика для продавцов Ozon — локально, из коробки</p>
        <form onSubmit={submit}>
          <label className="field">
            <span>Логин</span>
            <input
              className="input"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label className="field">
            <span>Пароль</span>
            <input
              className="input"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
            />
          </label>
          {error && <p className="form-error">{error}</p>}
          <button className="btn primary wide" disabled={busy || !username || !password}>
            {busy ? 'Подождите…' : mode === 'login' ? 'Войти' : 'Создать аккаунт'}
          </button>
        </form>
        <button className="linklike" onClick={switchMode}>
          {mode === 'login' ? 'Создать нового пользователя' : 'У меня уже есть аккаунт'}
        </button>
        {mode === 'login' && (
          <p className="hint">
            Учётная запись по умолчанию: <code>metrixsense</code> / <code>metrixsense</code> — смените пароль
            в <code>backend/.env</code>.
          </p>
        )}
      </main>
    </div>
  )
}
