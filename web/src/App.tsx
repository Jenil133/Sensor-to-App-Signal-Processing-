import type { ReactNode } from 'react'
import { BrowserRouter, HashRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { DEMO } from './api/demo'
import { AuthProvider, useAuth } from './auth/AuthContext'
import Dashboard from './pages/Dashboard'
import Devices from './pages/Devices'
import DeviceSim from './pages/DeviceSim'
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
        <NavLink to="/device-sim">Demo Device</NavLink>
        <button className="linklike" onClick={logout}>
          Log out
        </button>
      </nav>
      <main>{children}</main>
    </div>
  )
}

// HashRouter on the static demo host (GitHub Pages has no SPA rewrites)
const Router = DEMO ? HashRouter : BrowserRouter

export default function App() {
  return (
    <AuthProvider>
      <Router>
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
          <Route
            path="/device-sim"
            element={
              <Shell>
                <DeviceSim />
              </Shell>
            }
          />
        </Routes>
      </Router>
    </AuthProvider>
  )
}
