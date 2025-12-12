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

// Storage keys untuk cache
const USER_CACHE_KEY = 'se26_user_cache';
const AUTH_STATUS_KEY = 'se26_auth_status';
const AUTH_TIMESTAMP_KEY = 'se26_auth_timestamp';

// Cache validity duration (24 hours in milliseconds)
const CACHE_VALIDITY_MS = 24 * 60 * 60 * 1000;

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Inisialisasi user dari localStorage
  const [user, setUser] = useState<User | null>(() => {
    try {
      const cached = localStorage.getItem(USER_CACHE_KEY);
      const status = localStorage.getItem(AUTH_STATUS_KEY);
      const timestamp = localStorage.getItem(AUTH_TIMESTAMP_KEY);
      
      // Check if cache is still valid
      if (cached && status === 'authenticated' && timestamp) {
        const cacheAge = Date.now() - parseInt(timestamp, 10);
        if (cacheAge < CACHE_VALIDITY_MS) {
          console.log('[Auth] Restored user from cache (age:', Math.round(cacheAge / 1000 / 60), 'minutes)');
          return JSON.parse(cached);
        } else {
          console.log('[Auth] Cache expired, will re-validate');
        }
      }
    } catch (e) {
      console.error('[Auth] Failed to parse cached user:', e);
    }
    return null;
  });
  
  // Jika ada cached user yang valid, loading = false
  const [loading, setLoading] = useState<boolean>(() => {
    const status = localStorage.getItem(AUTH_STATUS_KEY);
    const cached = localStorage.getItem(USER_CACHE_KEY);
    const timestamp = localStorage.getItem(AUTH_TIMESTAMP_KEY);
    
    if (status === 'authenticated' && cached && timestamp) {
      const cacheAge = Date.now() - parseInt(timestamp, 10);
      if (cacheAge < CACHE_VALIDITY_MS) {
        return false; // Don't show loading if we have valid cache
      }
    }
    return true;
  });
  
  const navigate = useNavigate();
  const location = useLocation();
  
  const isCheckingAuth = useRef(false);
  const lastAuthCheck = useRef<number>(0);
  const AUTH_CHECK_INTERVAL = 30000; // 30 seconds between checks

  const isAuthenticated = user !== null;

  // Save user to cache with timestamp
  const saveUserToCache = useCallback((userData: User | null) => {
    if (userData) {
      localStorage.setItem(USER_CACHE_KEY, JSON.stringify(userData));
      localStorage.setItem(AUTH_STATUS_KEY, 'authenticated');
      localStorage.setItem(AUTH_TIMESTAMP_KEY, Date.now().toString());
      console.log('[Auth] User cached successfully');
    } else {
      localStorage.removeItem(USER_CACHE_KEY);
      localStorage.removeItem(AUTH_STATUS_KEY);
      localStorage.removeItem(AUTH_TIMESTAMP_KEY);
    }
  }, []);

  // Clear all auth data
  const clearAuthData = useCallback(() => {
    console.log('[Auth] Clearing all auth data');
    localStorage.removeItem(USER_CACHE_KEY);
    localStorage.removeItem(AUTH_STATUS_KEY);
    localStorage.removeItem(AUTH_TIMESTAMP_KEY);
    sessionStorage.removeItem('just_authenticated');
    setUser(null);
  }, []);

  const checkAuth = useCallback(async () => {
    // Skip auth check on public pages
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
    
    // Prevent too frequent checks if we already have a user
    const now = Date.now();
    if (user !== null && now - lastAuthCheck.current < AUTH_CHECK_INTERVAL) {
      console.log('[Auth] Auth check too recent, using cached user');
      setLoading(false);
      return;
    }

    // If we have a valid cached user, don't block the UI
    // Just validate in background
    const hasCachedUser = user !== null;
    if (hasCachedUser) {
      setLoading(false); // Don't show loading spinner
    }
    
    isCheckingAuth.current = true;
    lastAuthCheck.current = now;

    try {
      // Check for just authenticated flag
      const justAuth = sessionStorage.getItem('just_authenticated');
      if (justAuth) {
        sessionStorage.removeItem('just_authenticated');
        console.log('[Auth] Just authenticated flag found');
      }

      console.log('[Auth] Validating session with backend...');
      const response = await api.get('/auth/me');
      
      if (response.data.success && response.data.user) {
        console.log('[Auth] Session valid, user:', response.data.user.email);
        setUser(response.data.user);
        saveUserToCache(response.data.user);
      } else {
        console.log('[Auth] Session invalid: no user in response');
        // Only clear if we don't have cached user or response explicitly says invalid
        if (!hasCachedUser) {
          clearAuthData();
        }
      }
    } catch (error: any) {
      const status = error.response?.status;
      console.log('[Auth] Auth check error, status:', status);
      
      if (status === 401) {
        // 401 means definitely not authenticated
        // But check if this might be a cookie issue
        const hasCached = localStorage.getItem(USER_CACHE_KEY);
        
        if (hasCached) {
          console.log('[Auth] Got 401 but have cached user - possible cookie issue');
          // Keep the cached user for now, let user continue
          // They'll get 401 on actual API calls and can re-login then
          
          // Check cache age
          const timestamp = localStorage.getItem(AUTH_TIMESTAMP_KEY);
          if (timestamp) {
            const cacheAge = Date.now() - parseInt(timestamp, 10);
            // If cache is less than 1 hour old, trust it
            if (cacheAge < 60 * 60 * 1000) {
              console.log('[Auth] Cache is recent, keeping user logged in');
              setLoading(false);
              isCheckingAuth.current = false;
              return;
            }
          }
        }
        
        console.log('[Auth] Clearing auth data due to 401');
        clearAuthData();
      } else {
        // Network error or other issue - keep cached user if available
        console.log('[Auth] Network/server error, keeping cached session if available');
        if (!hasCachedUser) {
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
        saveUserToCache(response.data.user);
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
        saveUserToCache(response.data.user);
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
      clearAuthData();
      lastAuthCheck.current = 0;
      navigate('/login');
    }
  };

  // Effect untuk validasi session
  useEffect(() => {
    const publicPaths = ['/login', '/register', '/auth/callback'];
    
    if (publicPaths.includes(location.pathname)) {
      console.log('[Auth] Public page, skipping auth check');
      setLoading(false);
      return;
    }

    // If we have a user from cache, show the UI immediately
    // and validate in background
    if (user) {
      console.log('[Auth] Have cached user, showing UI immediately');
      setLoading(false);
      
      // Background validation (non-blocking)
      // Only check if last check was more than interval ago
      const now = Date.now();
      if (now - lastAuthCheck.current > AUTH_CHECK_INTERVAL) {
        checkAuth();
      }
    } else {
      // No cached user, need to check auth
      console.log('[Auth] No cached user, checking auth...');
      checkAuth();
    }
  }, [location.pathname]); // Intentionally not including checkAuth to avoid loops

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