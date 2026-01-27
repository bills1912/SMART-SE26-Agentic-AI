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
  loginWithGoogle: () => void;
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
    
    // Check for just_authenticated flag - skip loading entirely
    const justAuth = sessionStorage.getItem('just_authenticated');
    if (justAuth && cached) {
      return false;
    }
    
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
  const hasCheckedAfterOAuth = useRef(false);
  const AUTH_CHECK_INTERVAL = 60000; // 60 seconds between checks (increased)

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
    sessionStorage.removeItem('oauth_session_token');
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

    // Check for just_authenticated flag - trust the cache completely
    const justAuth = sessionStorage.getItem('just_authenticated');
    if (justAuth && !hasCheckedAfterOAuth.current) {
      console.log('[Auth] Just authenticated, trusting cache');
      sessionStorage.removeItem('just_authenticated');
      hasCheckedAfterOAuth.current = true;
      
      // Load user from cache if not already loaded
      if (!user) {
        try {
          const cached = localStorage.getItem(USER_CACHE_KEY);
          if (cached) {
            const cachedUser = JSON.parse(cached);
            setUser(cachedUser);
            console.log('[Auth] Loaded user from cache after OAuth:', cachedUser.email);
          }
        } catch (e) {
          console.error('[Auth] Failed to load cached user:', e);
        }
      }
      
      setLoading(false);
      lastAuthCheck.current = Date.now();
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
    const hasCachedUser = user !== null;
    if (hasCachedUser) {
      setLoading(false); // Don't show loading spinner
    }
    
    isCheckingAuth.current = true;
    lastAuthCheck.current = now;

    try {
      console.log('[Auth] Validating session with backend...');
      
      // Check if we have OAuth session token
      const oauthToken = sessionStorage.getItem('oauth_session_token');
      const headers: Record<string, string> = {};
      if (oauthToken) {
        headers['Authorization'] = `Bearer ${oauthToken}`;
        sessionStorage.removeItem('oauth_session_token'); // Use once
      }
      
      const response = await api.get('/auth/me', { headers });
      
      if (response.data.success && response.data.user) {
        console.log('[Auth] Session valid, user:', response.data.user.email);
        setUser(response.data.user);
        saveUserToCache(response.data.user);
      } else {
        console.log('[Auth] Session invalid: no user in response');
        if (!hasCachedUser) {
          clearAuthData();
        }
      }
    } catch (error: any) {
      const status = error.response?.status;
      console.log('[Auth] Auth check error, status:', status);
      
      if (status === 401) {
        // Check if we have recent cache - don't clear immediately
        const timestamp = localStorage.getItem(AUTH_TIMESTAMP_KEY);
        if (timestamp && hasCachedUser) {
          const cacheAge = Date.now() - parseInt(timestamp, 10);
          // If cache is less than 5 minutes old, trust it (OAuth just happened)
          if (cacheAge < 5 * 60 * 1000) {
            console.log('[Auth] Got 401 but cache is very recent, keeping user logged in');
            setLoading(false);
            isCheckingAuth.current = false;
            return;
          }
          // If cache is less than 1 hour old, also trust it
          if (cacheAge < 60 * 60 * 1000) {
            console.log('[Auth] Got 401 but cache is recent, keeping user logged in');
            setLoading(false);
            isCheckingAuth.current = false;
            return;
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
        hasCheckedAfterOAuth.current = true;
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
        hasCheckedAfterOAuth.current = true;
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

  // Google OAuth login - redirect to backend
  const loginWithGoogle = useCallback(() => {
    console.log('[Auth] Initiating Google OAuth...');
    
    // Get backend URL - try multiple sources
    let backendUrl = '';
    
    // Try Vite env
    if (typeof import.meta !== 'undefined' && process.env) {
      backendUrl = process.env.VITE_BACKEND_URL || '';
    }
    
    // Try CRA env
    if (!backendUrl && typeof process !== 'undefined' && process.env) {
      backendUrl = process.env.REACT_APP_BACKEND_URL || '';
    }
    
    // Fallback: construct from current origin for same-origin setup
    // Or use known backend URL for cross-origin
    if (!backendUrl) {
      // Check if we're on the frontend domain
      if (window.location.hostname.includes('web.up.railway.app')) {
        // Replace 'web' with backend pattern
        backendUrl = window.location.origin.replace('-web.up.railway.app', '.up.railway.app');
      } else {
        backendUrl = window.location.origin;
      }
    }
    
    console.log('[Auth] Using backend URL:', backendUrl);
    
    // Redirect to backend Google OAuth endpoint
    window.location.href = `${backendUrl}/api/auth/google/login`;
  }, []);

  const logout = async () => {
    try {
      console.log('[Auth] Logging out...');
      await api.post('/auth/logout');
    } catch (error) {
      console.debug('[Auth] Logout request completed');
    } finally {
      clearAuthData();
      lastAuthCheck.current = 0;
      hasCheckedAfterOAuth.current = false;
      navigate('/login');
    }
  };

  // Effect untuk validasi session - SIMPLIFIED
  useEffect(() => {
    const publicPaths = ['/login', '/register', '/auth/callback'];
    
    if (publicPaths.includes(location.pathname)) {
      console.log('[Auth] Public page, skipping auth check');
      setLoading(false);
      return;
    }

    // Check for just_authenticated flag FIRST
    const justAuth = sessionStorage.getItem('just_authenticated');
    if (justAuth) {
      console.log('[Auth] Just authenticated flag found, loading from cache');
      
      // Load from cache directly
      try {
        const cached = localStorage.getItem(USER_CACHE_KEY);
        if (cached) {
          const cachedUser = JSON.parse(cached);
          if (!user || user.email !== cachedUser.email) {
            setUser(cachedUser);
          }
          console.log('[Auth] User loaded from cache:', cachedUser.email);
        }
      } catch (e) {
        console.error('[Auth] Failed to parse cached user:', e);
      }
      
      sessionStorage.removeItem('just_authenticated');
      setLoading(false);
      lastAuthCheck.current = Date.now();
      return;
    }

    // If we have a user from cache, show the UI immediately
    if (user) {
      console.log('[Auth] Have cached user, showing UI immediately');
      setLoading(false);
      
      // Background validation only if last check was long ago
      const now = Date.now();
      if (now - lastAuthCheck.current > AUTH_CHECK_INTERVAL) {
        // Delay the check to not block initial render
        setTimeout(() => {
          checkAuth();
        }, 1000);
      }
    } else {
      // No cached user, need to check auth
      console.log('[Auth] No cached user, checking auth...');
      checkAuth();
    }
  }, [checkAuth, location.pathname, user]); // Intentionally minimal dependencies

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        loading,
        login,
        register,
        logout,
        checkAuth,
        loginWithGoogle
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