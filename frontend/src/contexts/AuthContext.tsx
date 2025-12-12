import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../services/api';

interface User {
  user_id: string;
  email: string;
  name: string;
  picture?: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ===== KUNCI PERBAIKAN: Storage keys untuk cache =====
const USER_CACHE_KEY = 'se26_user_cache';
const AUTH_STATUS_KEY = 'se26_auth_status';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // ===== PERBAIKAN 1: Inisialisasi user dari localStorage =====
  const [user, setUser] = useState<User | null>(() => {
    try {
      const cached = localStorage.getItem(USER_CACHE_KEY);
      const status = localStorage.getItem(AUTH_STATUS_KEY);
      if (cached && status === 'authenticated') {
        console.log('[Auth] Restored user from cache');
        return JSON.parse(cached);
      }
    } catch (e) {
      console.error('[Auth] Failed to parse cached user:', e);
    }
    return null;
  });
  
  // ===== PERBAIKAN 2: Jika ada cached user, loading = false =====
  const [loading, setLoading] = useState<boolean>(() => {
    const status = localStorage.getItem(AUTH_STATUS_KEY);
    const cached = localStorage.getItem(USER_CACHE_KEY);
    // Jika sudah ada cache, tidak perlu loading state
    if (status === 'authenticated' && cached) {
      return false;
    }
    return true;
  });
  
  const navigate = useNavigate();
  const location = useLocation();
  
  const isCheckingAuth = useRef(false);
  const lastAuthCheck = useRef<number>(0);
  const AUTH_CHECK_INTERVAL = 5000;

  const isAuthenticated = user !== null;

  // ===== PERBAIKAN 3: Sync user ke localStorage =====
  const saveUserToCache = useCallback((userData: User | null) => {
    if (userData) {
      localStorage.setItem(USER_CACHE_KEY, JSON.stringify(userData));
      localStorage.setItem(AUTH_STATUS_KEY, 'authenticated');
    } else {
      localStorage.removeItem(USER_CACHE_KEY);
      localStorage.removeItem(AUTH_STATUS_KEY);
    }
  }, []);

  // ===== Clear semua auth data =====
  const clearAuthData = useCallback(() => {
    localStorage.removeItem(USER_CACHE_KEY);
    localStorage.removeItem(AUTH_STATUS_KEY);
    sessionStorage.removeItem('just_authenticated');
    setUser(null);
  }, []);

  const checkAuth = useCallback(async () => {
    // Skip auth check di halaman public
    const publicPaths = ['/login', '/register', '/auth/callback'];
    if (publicPaths.includes(location.pathname)) {
      console.log('[Auth] Skipping auth check on public page:', location.pathname);
      setLoading(false);
      return;
    }

    // Prevent duplicate concurrent calls
    if (isCheckingAuth.current) {
      console.log('[Auth] Auth check already in progress, skipping...');
      return;
    }
    
    // Prevent too frequent checks (kecuali belum punya user)
    const now = Date.now();
    if (now - lastAuthCheck.current < AUTH_CHECK_INTERVAL && user !== null) {
      console.log('[Auth] Auth check too recent, skipping...');
      setLoading(false);
      return;
    }
    
    isCheckingAuth.current = true;
    lastAuthCheck.current = now;

    try {
      const justAuth = sessionStorage.getItem('just_authenticated');
      if (justAuth) {
        sessionStorage.removeItem('just_authenticated');
        console.log('[Auth] Just authenticated, proceeding immediately...');
      }

      console.log('[Auth] Checking auth status with backend...');
      const response = await api.get('/auth/me');
      
      if (response.data.success && response.data.user) {
        console.log('[Auth] Auth check successful, user:', response.data.user.email);
        setUser(response.data.user);
        saveUserToCache(response.data.user); // ===== Simpan ke cache =====
      } else {
        console.log('[Auth] Auth check failed: no user in response');
        clearAuthData();
      }
    } catch (error: any) {
      if (error.response?.status === 401) {
        console.log('[Auth] Not authenticated (401) - clearing cache');
        clearAuthData();
      } else {
        // ===== PERBAIKAN 4: Jika network error tapi ada cache, tetap gunakan cache =====
        console.error('[Auth] Auth check error:', error.message);
        const cached = localStorage.getItem(USER_CACHE_KEY);
        if (cached) {
          console.log('[Auth] Network error but have cached user, keeping session');
          // Tidak clear auth data, biarkan user tetap login
        } else {
          clearAuthData();
        }
      }
    } finally {
      setLoading(false);
      isCheckingAuth.current = false;
    }
  }, [location.pathname, user, saveUserToCache, clearAuthData]);

  const login = async (email: string, password: string) => {
    try {
      console.log('[Auth] Attempting login for:', email);
      const response = await api.post('/auth/login', { email, password });
      
      if (response.data.success && response.data.user) {
        console.log('[Auth] Login successful');
        setUser(response.data.user);
        saveUserToCache(response.data.user); // ===== Simpan ke cache =====
        sessionStorage.setItem('just_authenticated', 'true');
        lastAuthCheck.current = Date.now();
        navigate('/dashboard');
      } else {
        throw new Error('Login failed: Invalid response');
      }
    } catch (error: any) {
      console.error('[Auth] Login error:', error);
      const message = error.response?.data?.detail || error.message || 'Login failed';
      throw new Error(message);
    }
  };

  const register = async (email: string, password: string, name: string) => {
    try {
      console.log('[Auth] Attempting registration for:', email);
      const response = await api.post('/auth/register', { email, password, name });
      
      if (response.data.success && response.data.user) {
        console.log('[Auth] Registration successful');
        setUser(response.data.user);
        saveUserToCache(response.data.user); // ===== Simpan ke cache =====
        sessionStorage.setItem('just_authenticated', 'true');
        lastAuthCheck.current = Date.now();
        navigate('/dashboard');
      } else {
        throw new Error('Registration failed: Invalid response');
      }
    } catch (error: any) {
      console.error('[Auth] Registration error:', error);
      const message = error.response?.data?.detail || error.message || 'Registration failed';
      throw new Error(message);
    }
  };

  const logout = async () => {
    try {
      console.log('[Auth] Logging out...');
      await api.post('/auth/logout');
    } catch (error) {
      console.debug('[Auth] Logout request completed');
    } finally {
      clearAuthData(); // ===== Clear cache saat logout =====
      lastAuthCheck.current = 0;
      navigate('/login');
    }
  };

  // ===== PERBAIKAN 5: Effect untuk validasi session di background =====
  useEffect(() => {
    const publicPaths = ['/login', '/register', '/auth/callback'];
    
    if (publicPaths.includes(location.pathname)) {
      console.log('[Auth] Public page, skipping auth check');
      setLoading(false);
      return;
    }

    // Jika sudah ada user dari cache, langsung set loading false
    // tapi tetap validasi di background
    if (user) {
      setLoading(false);
      // Background validation (non-blocking)
      checkAuth();
    } else {
      // Tidak ada cache, harus check dulu
      checkAuth();
    }
  }, [location.pathname]); // Hapus checkAuth dari dependency untuk avoid loop

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        loading,
        login,
        register,
        logout,
        checkAuth
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};