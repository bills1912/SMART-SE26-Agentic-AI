import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

// Storage keys (harus sama dengan AuthContext)
const USER_CACHE_KEY = 'se26_user_cache';
const AUTH_STATUS_KEY = 'se26_auth_status';

const AuthCallback: React.FC = () => {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const processOAuth = async () => {
      try {
        // Extract session_id from URL fragment
        const hash = window.location.hash;
        const params = new URLSearchParams(hash.substring(1));
        const sessionId = params.get('session_id');

        if (!sessionId) {
          throw new Error('No session_id found in URL');
        }

        console.log('[AuthCallback] Processing OAuth with session_id');

        // Send session_id to backend
        const response = await api.post('/auth/oauth/callback', {
          session_id: sessionId
        });

        if (response.data.success) {
          console.log('[AuthCallback] OAuth successful');
          
          // ===== PERBAIKAN: Simpan user ke localStorage SEBELUM redirect =====
          if (response.data.user) {
            localStorage.setItem(USER_CACHE_KEY, JSON.stringify(response.data.user));
            localStorage.setItem(AUTH_STATUS_KEY, 'authenticated');
            console.log('[AuthCallback] User cached to localStorage');
          }
          
          // Set flag untuk skip delay
          sessionStorage.setItem('just_authenticated', 'true');
          
          // Redirect ke dashboard
          // Gunakan navigate untuk SPA routing yang lebih smooth
          navigate('/dashboard', { replace: true });
        } else {
          throw new Error(response.data.message || 'OAuth failed');
        }
      } catch (error: any) {
        console.error('[AuthCallback] OAuth error:', error);
        setError(error.message || 'Authentication failed');
        
        // Redirect ke login setelah delay
        setTimeout(() => {
          navigate('/login', { replace: true });
        }, 3000);
      }
    };

    processOAuth();
  }, [navigate]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-orange-50 via-white to-red-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
        <div className="text-center max-w-md p-8 bg-white dark:bg-gray-800 rounded-2xl shadow-xl">
          <div className="text-red-500 text-5xl mb-4">⚠️</div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Authentication Failed
          </h2>
          <p className="text-gray-600 dark:text-gray-300 mb-4">{error}</p>
          <p className="text-sm text-gray-500">Redirecting to login...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-orange-50 via-white to-red-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
      <div className="text-center">
        <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-orange-600 mx-auto mb-4"></div>
        <p className="text-gray-600 dark:text-gray-300 text-lg">Completing sign in...</p>
      </div>
    </div>
  );
};

export default AuthCallback;