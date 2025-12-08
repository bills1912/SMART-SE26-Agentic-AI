import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Database } from 'lucide-react';
import { ChatMessage } from '../types/chat';
import MessageBubble from './MessageBubble';
import { toast } from '../hooks/use-toast';
import apiService from '../services/api';
import ThemeToggle from './ThemeToggle';
import ChatSidebar from './ChatSidebar';
import SidebarToggle from './SidebarToggle';
import CollapsedSidebar from './CollapsedSidebar';
import UserMenu from './UserMenu';
import { useChat } from '../contexts/ChatContext';

const ChatInterface: React.FC = () => {
  const { 
    currentSession, 
    addMessageToCurrentSession,
    createNewChat,
    exportCurrentChat
  } = useChat();
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [scrapingStatus, setScrapingStatus] = useState<'idle' | 'in_progress'>('idle');
  const [isBackendAvailable, setIsBackendAvailable] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Get messages from current session
  const messages = currentSession?.messages || [];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Check backend availability and get initial status
    checkBackendStatus();
  }, []);

  const checkBackendStatus = async () => {
    try {
      const available = await apiService.isBackendAvailable();
      setIsBackendAvailable(available);
      
      if (available) {
        const health = await apiService.getHealth();
        setScrapingStatus(health.scraping_status);
      }
    } catch (error) {
      setIsBackendAvailable(false);
      console.error('Backend not available:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading || !currentSession) return;

    const userMessage: ChatMessage = {
      id: Math.random().toString(36).substr(2, 9),
      session_id: currentSession.id || '',
      sender: 'user',
      content: inputMessage.trim(),
      timestamp: new Date(),
    };

    // Add user message to session
    addMessageToCurrentSession(userMessage);
    
    const originalMessage = inputMessage.trim();
    setInputMessage('');
    setIsLoading(true);

    try {
      if (!isBackendAvailable) {
        throw new Error('Backend service is currently unavailable');
      }

      // Call real API
      const response = await apiService.sendMessage(originalMessage, currentSession.id);
      
      // Create AI response message
      const aiResponse: ChatMessage = {
        id: response.session_id + '_' + Date.now(),
        session_id: response.session_id,
        sender: 'ai',
        content: response.message,
        timestamp: new Date(),
        visualizations: response.visualizations || [],
        insights: response.insights || [],
        policies: response.policies || [],
      };
      
      // Add AI response to session
      addMessageToCurrentSession(aiResponse);
      
      toast({
        title: "Analysis Complete",
        description: `AI policy analysis generated successfully. ${response.supporting_data_count > 0 ? `Used ${response.supporting_data_count} data sources.` : ''}`,
      });

      // Update scraping status
      const health = await apiService.getHealth();
      setScrapingStatus(health.scraping_status);
      
    } catch (error: any) {
      console.error('Error sending message:', error);
      
      // Fallback response for errors
      const errorResponse: ChatMessage = {
        id: 'error_' + Date.now(),
        session_id: currentSession.id || '',
        sender: 'ai',
        content: 'I apologize, but I encountered an issue while analyzing your policy question. This could be due to high demand or temporary service issues. Please try again in a moment.',
        timestamp: new Date(),
      };
      
      addMessageToCurrentSession(errorResponse);
      
      toast({
        title: "Connection Error",
        description: isBackendAvailable 
          ? "Failed to analyze policy. Please try again." 
          : "AI service is temporarily unavailable. Please check your connection.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-white to-red-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 transition-colors duration-300">
      {/* Chat Sidebar - Full when open */}
      <ChatSidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />
      
      {/* Collapsed Sidebar - Icons only when sidebar closed */}
      {!sidebarOpen && (
        <CollapsedSidebar
          onNewChat={createNewChat}
          onShowHistory={() => setSidebarOpen(true)}
          onExport={exportCurrentChat}
        />
      )}
      
      {/* Main Content - Claude-style FULL WIDTH elegant layout */}
      <div className={`flex-1 flex flex-col h-screen transition-all duration-300 ${
        sidebarOpen ? 'ml-80' : 'ml-16'
      }`}>
        {/* Elegant Header - FULL WIDTH dari kiri ke kanan */}
        <div className="border-b border-gray-200 dark:border-gray-700 px-8 py-4">
          <div className="flex items-center justify-between">
            {/* Left: Title */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-red-500 to-orange-600 rounded-lg flex items-center justify-center">
                <Bot className="h-4 w-4 text-white" />
              </div>
              <h1 className="text-xl font-semibold text-gray-800 dark:text-white">
                AI Policy & Insight Generator
              </h1>
            </div>
            
            {/* Right: Controls */}
            <div className="flex items-center gap-3">
              <ThemeToggle />
              <UserMenu />
            </div>
          </div>
        </div>

        {/* Chat Messages Area - Claude-style FULL WIDTH clean & spacious */}
        <div className="flex-1 overflow-y-auto" style={{ minHeight: 0 }}>
          <div className="max-w-5xl mx-auto px-8 py-8">
            <div className="space-y-10">
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {isLoading && (
                <div className="flex items-center gap-3 p-4">
                  <div className="w-8 h-8 bg-gradient-to-br from-red-500 to-orange-600 rounded-full flex items-center justify-center">
                    <Bot className="h-4 w-4 text-white" />
                  </div>
                  <div className="flex items-center gap-2 text-gray-600 dark:text-gray-200">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>
                      {scrapingStatus === 'in_progress' 
                        ? 'Gathering latest policy data...' 
                        : 'Analyzing policy scenario...'}
                    </span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>

        {/* Input Area - Claude-style elegant FULL WIDTH */}
        <div className="flex-shrink-0 border-t border-gray-200 dark:border-gray-700">
          <div className="max-w-5xl mx-auto px-8 py-6">
            <div className="relative">
              <textarea
                ref={textareaRef}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Reply..."
                className="w-full px-5 py-4 pr-14 border border-gray-300 dark:border-gray-600 rounded-3xl focus:outline-none focus:ring-2 focus:ring-orange-500 dark:focus:ring-orange-400 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 resize-none transition-all duration-200 text-base"
                style={{ minHeight: '56px', maxHeight: '200px' }}
                disabled={isLoading}
                rows={1}
              />
              <button
                onClick={handleSendMessage}
                disabled={isLoading || !inputMessage.trim()}
                className="absolute right-3 bottom-3 p-3 bg-gradient-to-r from-red-500 to-orange-600 hover:from-red-600 hover:to-orange-700 text-white rounded-2xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-md"
                title={isLoading ? "Analyzing..." : "Send message"}
              >
                {isLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Send className="h-5 w-5" />
                )}
              </button>
            </div>
            
            {/* AI Disclaimer & Status - Claude-style */}
            <div className="flex items-center justify-between mt-4 text-xs text-gray-500 dark:text-gray-400">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5">
                  <Database className="h-3 w-3" />
                  <span className={scrapingStatus === 'in_progress' ? 'text-orange-600 dark:text-orange-400' : ''}>
                    {scrapingStatus === 'in_progress' ? 'Gathering data...' : 'Data ready'}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className={`w-1.5 h-1.5 rounded-full ${isBackendAvailable ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className={isBackendAvailable ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                    {isBackendAvailable ? 'Connected' : 'Offline'}
                  </span>
                </div>
              </div>
              <p className="text-gray-500 dark:text-gray-400">
                AI can make mistakes. Please verify important information.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;