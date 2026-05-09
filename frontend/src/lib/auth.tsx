import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from './api'

export interface AuthUser {
  id: string
  username: string
  display_name: string
  email: string
  is_active: boolean
}

interface AuthState {
  user: AuthUser | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  needsSetup: boolean | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const TOKEN_KEY = 'ts_token'
const USER_KEY = 'ts_user'

const AuthContext = createContext<AuthState | null>(null)

export const useAuth = (): AuthState => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      const raw = localStorage.getItem(USER_KEY)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [isLoading, setIsLoading] = useState(true)
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null)

  // Attach token to all API requests
  useEffect(() => {
    const interceptorId = api.interceptors.request.use((config) => {
      const currentToken = localStorage.getItem(TOKEN_KEY)
      if (currentToken) {
        config.headers.Authorization = `Bearer ${currentToken}`
      }
      return config
    })
    return () => api.interceptors.request.eject(interceptorId)
  }, [])

  // On mount: check bootstrap status and validate token
  useEffect(() => {
    const init = async () => {
      try {
        const { data } = await api.get<{ needs_setup: boolean }>('/auth/bootstrap')
        setNeedsSetup(data.needs_setup)

        if (token && !data.needs_setup) {
          try {
            const { data: userData } = await api.get('/users/me', {
              headers: { Authorization: `Bearer ${token}` },
            })
            setUser(userData as AuthUser)
            localStorage.setItem(USER_KEY, JSON.stringify(userData))
          } catch {
            // Token invalid — clear it
            localStorage.removeItem(TOKEN_KEY)
            localStorage.removeItem(USER_KEY)
            setToken(null)
            setUser(null)
          }
        }
      } catch {
        // API not reachable — allow through with existing state
      } finally {
        setIsLoading(false)
      }
    }
    init()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(async (username: string, password: string) => {
    const formData = new URLSearchParams()
    const loginEmail = username.includes('@') ? username : `${username}@threadsense.com`
    formData.append('username', loginEmail)
    formData.append('password', password)
    
    const { data } = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
    const access_token = data.access_token
    localStorage.setItem(TOKEN_KEY, access_token)
    setToken(access_token)
    
    // Fetch user details from /users/me
    const { data: userData } = await api.get('/users/me', {
      headers: { Authorization: `Bearer ${access_token}` }
    })
    
    localStorage.setItem(USER_KEY, JSON.stringify(userData))
    setUser(userData)
    setNeedsSetup(false)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const refreshUser = useCallback(async () => {
    if (!token) return
    try {
      const { data } = await api.get('/users/me')
      setUser(data as AuthUser)
      localStorage.setItem(USER_KEY, JSON.stringify(data))
    } catch {
      // ignore
    }
  }, [token])

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        needsSetup,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
