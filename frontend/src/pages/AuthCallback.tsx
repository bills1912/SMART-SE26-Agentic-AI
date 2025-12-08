import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';

const AuthCallback: React.FC = () => {
  const navigate = useNavigate();
  const { checkAuth } = useAuth();

  useEffect(() => {
    const processOAuth = async () => {
      try {
        // Extract session_id from URL fragment
        const hash = window.location.hash;
        const params = new URLSearchParams(hash.substring(1));
        const sessionId = params.get('session_id');

        if (!sessionId) {
          throw new Error('No session_id found');
        }

        // Send session_id to backend
        const response = await api.post('/auth/oauth/callback', {
          session_id: sessionId
        });

        if (response.data.success) {
          // Set flag to skip delay in checkAuth
          sessionStorage.setItem('just_authenticated', 'true');
          
          // Force full page reload to /dashboard to ensure proper routing
          window.location.href = '/dashboard';
        }
      } catch (error) {
        console.error('OAuth callback error:', error);
        window.location.href = '/login';
      }
    };

    processOAuth();
  }, []);

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
