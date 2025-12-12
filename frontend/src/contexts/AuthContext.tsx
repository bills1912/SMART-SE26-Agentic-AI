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

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  
  const isCheckingAuth = useRef(false);
  const lastAuthCheck = useRef<number>(0);
  const AUTH_CHECK_INTERVAL = 5000;

  const isAuthenticated = user !== null;

  const checkAuth = useCallback(async () => {
    // CRITICAL: Jangan check auth di halaman public
    const publicPaths = ['/login', '/register', '/auth/callback'];
    if (publicPaths.includes(location.pathname)) {
      console.log('Skipping auth check on public page:', location.pathname);
      setLoading(false);
      return;
    }

    // Prevent duplicate concurrent calls
    if (isCheckingAuth.current) {
      console.log('Auth check already in progress, skipping...');
      return;
    }
    
    // Prevent too frequent checks
    const now = Date.now();
    if (now - lastAuthCheck.current < AUTH_CHECK_INTERVAL && user !== null) {
      console.log('Auth check too recent, skipping...');
      setLoading(false);
      return;
    }
    
    isCheckingAuth.current = true;
    lastAuthCheck.current = now;

    try {
      const justAuth = sessionStorage.getItem('just_authenticated');
      if (justAuth) {
        sessionStorage.removeItem('just_authenticated');
        console.log('Just authenticated, proceeding immediately...');
      }

      console.log('Checking auth status...');
      const response = await api.get('/auth/me');
      
      if (response.data.success && response.data.user) {
        console.log('Auth check successful, user:', response.data.user.email);
        setUser(response.data.user);
      } else {
        console.log('Auth check failed: no user in response');
        setUser(null);
      }
    } catch (error: any) {
      if (error.response?.status !== 401) {
        console.error('Auth check error:', error.message);
      } else {
        console.log('Not authenticated (401)');
      }
      setUser(null);
    } finally {
      setLoading(false);
      isCheckingAuth.current = false;
    }
  }, [location.pathname, user]);

  const login = async (email: string, password: string) => {
    try {
      console.log('Attempting login for:', email);
      const response = await api.post('/auth/login', { email, password });
      
      if (response.data.success && response.data.user) {
        console.log('Login successful');
        setUser(response.data.user);
        sessionStorage.setItem('just_authenticated', 'true');
        lastAuthCheck.current = Date.now();
        navigate('/dashboard');
      } else {
        throw new Error('Login failed: Invalid response');
      }
    } catch (error: any) {
      console.error('Login error:', error);
      const message = error.response?.data?.detail || error.message || 'Login failed';
      throw new Error(message);
    }
  };

  const register = async (email: string, password: string, name: string) => {
    try {
      console.log('Attempting registration for:', email);
      const response = await api.post('/auth/register', { email, password, name });
      
      if (response.data.success && response.data.user) {
        console.log('Registration successful');
        setUser(response.data.user);
        sessionStorage.setItem('just_authenticated', 'true');
        lastAuthCheck.current = Date.now();
        navigate('/dashboard');
      } else {
        throw new Error('Registration failed: Invalid response');
      }
    } catch (error: any) {
      console.error('Registration error:', error);
      const message = error.response?.data?.detail || error.message || 'Registration failed';
      throw new Error(message);
    }
  };

  const logout = async () => {
    try {
      console.log('Logging out...');
      await api.post('/auth/logout');
    } catch (error) {
      console.debug('Logout request completed');
    } finally {
      setUser(null);
      lastAuthCheck.current = 0;
      navigate('/login');
    }
  };

  useEffect(() => {
    // CRITICAL: Only check auth on protected routes
    const publicPaths = ['/login', '/register', '/auth/callback'];
    
    if (publicPaths.includes(location.pathname)) {
      console.log('Public page, skipping auth check');
      setLoading(false);
      return;
    }

    checkAuth();
  }, [location.pathname, checkAuth]);

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