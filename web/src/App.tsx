import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import Dashboard from './pages/Dashboard'
import Devices from './pages/Devices'
import Login from './pages/Login'
import './App.css'

function Shell({ children }: { children: ReactNode }) {
  const { authed, logout } = useAuth()
  if (!authed) return <Navigate to="/login" replace />
  return (
    <div className="shell">
      <nav className="topnav">
        <span className="brand">
          <span className="brand-pulse" />
          Baseline
        </span>
        <NavLink to="/" end>
          Dashboard
        </NavLink>
        <NavLink to="/devices">Devices</NavLink>
        <button className="linklike" onClick={logout}>
          Log out
        </button>
      </nav>
      <main>{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <Shell>
                <Dashboard />
              </Shell>
            }
          />
          <Route
            path="/devices"
            element={
              <Shell>
                <Devices />
              </Shell>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
