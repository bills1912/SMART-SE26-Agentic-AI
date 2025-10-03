import React from 'react';
import './App.css';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ChatInterface from './components/ChatInterface';
import { Toaster } from './components/ui/toaster';
import { ThemeProvider } from './contexts/ThemeContext';
import { ChatProvider } from './contexts/ChatContext';

function App() {
  return (
    <ThemeProvider>
      <ChatProvider>
        <div className="App min-h-screen bg-gradient-to-br from-orange-50 via-white to-red-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 transition-colors duration-300">
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<ChatInterface />} />
            </Routes>
          </BrowserRouter>
          <Toaster />
        </div>
      </ChatProvider>
    </ThemeProvider>
  );
}

export default App;