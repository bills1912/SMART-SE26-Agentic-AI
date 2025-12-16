// App.tsx
import React from 'react';
import './App.css';
// 1. IMPORT ROUTES (Pastikan navigate & location ada, tapi di sini kita hanya ubah Route)
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import ChatInterface from './components/ChatInterface';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import AuthCallback from './pages/AuthCallback';
import ProtectedRoute from './components/ProtectedRoute';
import { Toaster } from './components/ui/toaster';
import { ThemeProvider } from './contexts/ThemeContext';
import { ChatProvider } from './contexts/ChatContext';
import { AuthProvider } from './contexts/AuthContext';

function AppRouter() {
  const location = useLocation();

  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      
      {/* Route untuk New Chat (Dashboard default) */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <ChatInterface />
          </ProtectedRoute>
        }
      />

      {/* 2. TAMBAHKAN ROUTE KHUSUS UNTUK CHAT HISTORY / AKTIF */}
      <Route
        path="/c/:sessionId"
        element={
          <ProtectedRoute>
            <ChatInterface />
          </ProtectedRoute>
        }
      />
      
      <Route 
        path="/" 
        element={<Navigate to="/dashboard" replace />}
      />
      
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          {/* ChatProvider harus di dalam BrowserRouter jika ingin akses hooks router di dalamnya, 
              tapi di sini strukturnya sudah aman karena AppRouter ada di dalamnya */}
          <ChatProvider>
            <div className="App min-h-screen bg-gradient-to-br from-orange-50 via-white to-red-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 transition-colors duration-300">
              <AppRouter />
              <Toaster />
            </div>
          </ChatProvider>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;