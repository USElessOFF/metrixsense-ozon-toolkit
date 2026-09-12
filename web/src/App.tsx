import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { api } from './api/client'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { Layout } from './components/Layout'
import { Spinner } from './components/ui'
import { Toasts } from './components/Toast'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import Stocks from './pages/Stocks'
import Prices from './pages/Prices'
import ProductCards from './pages/ProductCards'
import Finance from './pages/Finance'
import Cashflow from './pages/Cashflow'
import SearchQueries from './pages/SearchQueries'
import Rating from './pages/Rating'
import Calculator from './pages/Calculator'
import Analogs from './pages/Analogs'
import Reports from './pages/Reports'
import Compare from './pages/Compare'
import Settings from './pages/Settings'

function Boot() {
  return (
    <div className="boot">
      <Spinner />
    </div>
  )
}

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Boot />
  return user ? children : <Navigate to="/login" replace />
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Boot />
  return user ? <Navigate to="/" replace /> : children
}

export default function App() {
  const navigate = useNavigate()

  useEffect(
    () => api.onUnauthorized(() => navigate('/login')),
    [navigate],
  )

  return (
    <AuthProvider>
      <Toasts />
      <Routes>
        <Route
          path="/login"
          element={
            <GuestOnly>
              <Login />
            </GuestOnly>
          }
        />
        <Route
          element={
            <Protected>
              <Layout />
            </Protected>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="onboarding" element={<Onboarding />} />
          <Route path="stocks" element={<Stocks />} />
          <Route path="prices" element={<Prices />} />
          <Route path="cards" element={<ProductCards />} />
          <Route path="finance" element={<Finance />} />
          <Route path="cashflow" element={<Cashflow />} />
          <Route path="queries" element={<SearchQueries />} />
          <Route path="rating" element={<Rating />} />
          <Route path="calculator" element={<Calculator />} />
          <Route path="analogs" element={<Analogs />} />
          <Route path="report" element={<Reports />} />
          <Route path="compare" element={<Compare />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
