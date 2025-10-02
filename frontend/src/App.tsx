import React from 'react';
import './App.css';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ChatInterface from './components/ChatInterface';
import { Toaster } from './components/ui/toaster';

function App() {
  return (
    <div className="App min-h-screen bg-gradient-to-br from-orange-50 via-white to-red-50">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ChatInterface />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </div>
  );
}

export default App;