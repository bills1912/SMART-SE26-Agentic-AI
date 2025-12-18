import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

// Storage keys (harus sama dengan AuthContext)
const USER_CACHE_KEY = 'se26_user_cache';
const AUTH_STATUS_KEY = 'se26_auth_status';
const AUTH_TIMESTAMP_KEY = 'se26_auth_timestamp';

const AuthCallback: React.FC = () => {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('Processing...');

  useEffect(() => {
    const processOAuth = async () => {
      try {
        // Extract data from URL fragment (hash)
        // Backend redirects with: /auth/callback#session_token=xxx&user_id=xxx&email=xxx&name=xxx
        const hash = window.location.hash;
        
        if (!hash || hash.length <= 1) {
          // Check for error in query params
          const urlParams = new URLSearchParams(window.location.search);
          const errorParam = urlParams.get('error');
          
          if (errorParam) {
            throw new Error(`Authentication failed: ${errorParam}`);
          }
          
          throw new Error('No authentication data received');
        }
        
        // Parse fragment parameters
        const params = new URLSearchParams(hash.substring(1));
        const sessionToken = params.get('session_token');
        const userId = params.get('user_id');
        const email = params.get('email');
        const name = params.get('name');
        const picture = params.get('picture');

        console.log('[AuthCallback] Received OAuth data:', { 
          hasToken: !!sessionToken, 
          userId, 
          email 
        });

        if (!sessionToken) {
          throw new Error('No session token received');
        }

        if (!email) {
          throw new Error('No email received from authentication');
        }

        setStatus('Setting up your session...');

        // Construct user object
        const user = {
          user_id: userId || '',
          email: decodeURIComponent(email),
          name: name ? decodeURIComponent(name) : email.split('@')[0],
          picture: picture ? decodeURIComponent(picture) : null
        };

        // Save user to localStorage FIRST
        localStorage.setItem(USER_CACHE_KEY, JSON.stringify(user));
        localStorage.setItem(AUTH_STATUS_KEY, 'authenticated');
        localStorage.setItem(AUTH_TIMESTAMP_KEY, Date.now().toString());
        
        console.log('[AuthCallback] User cached to localStorage:', user.email);

        // Set flags untuk AuthContext
        sessionStorage.setItem('just_authenticated', 'true');
        sessionStorage.setItem('oauth_session_token', sessionToken);
        
        setStatus('Verifying session...');

        // Verify session dengan backend untuk memastikan cookie ter-set
        // Ini juga akan membantu set cookie jika belum
        try {
          const response = await api.get('/auth/me', {
            headers: {
              'Authorization': `Bearer ${sessionToken}`
            }
          });
          
          if (response.data.success && response.data.user) {
            console.log('[AuthCallback] Session verified with backend');
            // Update user data dengan data terbaru dari backend
            const verifiedUser = response.data.user;
            localStorage.setItem(USER_CACHE_KEY, JSON.stringify(verifiedUser));
          }
        } catch (verifyError) {
          // Jika verify gagal, tetap lanjut dengan cached data
          // Cookie mungkin sudah di-set oleh backend redirect
          console.log('[AuthCallback] Session verify skipped, using cached data');
        }

        setStatus('Redirecting to dashboard...');

        // Clear the hash from URL before redirect (security)
        window.history.replaceState(null, '', window.location.pathname);

        // Use window.location for full page reload to ensure clean state
        // This helps with cookie synchronization
        window.location.href = '/dashboard';
        
      } catch (error: any) {
        console.error('[AuthCallback] OAuth error:', error);
        setError(error.message || 'Authentication failed');
        
        // Clear any partial auth data
        localStorage.removeItem(USER_CACHE_KEY);
        localStorage.removeItem(AUTH_STATUS_KEY);
        localStorage.removeItem(AUTH_TIMESTAMP_KEY);
        sessionStorage.removeItem('just_authenticated');
        sessionStorage.removeItem('oauth_session_token');
        
        // Redirect ke login setelah delay
        setTimeout(() => {
          window.location.href = '/login';
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
        <p className="text-gray-600 dark:text-gray-300 text-lg">{status}</p>
      </div>
    </div>
  );
};

export default AuthCallback;