import { createContext, useCallback, useContext, useState } from 'react'
import type { ReactNode } from 'react'
import { api, getToken, setToken } from '../api/client'

interface AuthState {
  authed: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authed, setAuthed] = useState(() => getToken() !== null)

  const login = useCallback(async (email: string, password: string) => {
    const res = await api<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setToken(res.access_token)
    setAuthed(true)
  }, [])

  const register = useCallback(
    async (email: string, password: string) => {
      await api('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      await login(email, password)
    },
    [login],
  )

  const logout = useCallback(() => {
    setToken(null)
    setAuthed(false)
  }, [])

  return (
    <AuthContext.Provider value={{ authed, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}
