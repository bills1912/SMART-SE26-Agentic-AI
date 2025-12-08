import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Database } from 'lucide-react';
import { ChatMessage } from '../types/chat';
import MessageBubble from './MessageBubble';
import { toast } from '../hooks/use-toast';
import apiService from '../services/api';
import ThemeToggle from './ThemeToggle';
import ChatSidebar from './ChatSidebar';
import SidebarToggle from './SidebarToggle';
import UserMenu from './UserMenu';
import { useChat } from '../contexts/ChatContext';

const ChatInterface: React.FC = () => {
  const { currentSession, addMessageToCurrentSession } = useChat();
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
      {/* Chat Sidebar */}
      <ChatSidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />
      
      {/* Sidebar Toggle Button */}
      <SidebarToggle isOpen={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />
      
      {/* Main Content - Claude-style full-width elegant layout */}
      <div className={`flex-1 flex flex-col transition-all duration-300 ${
        sidebarOpen ? 'ml-80' : 'ml-0'
      }`}>
        <div className="max-w-4xl mx-auto w-full h-full flex flex-col px-6 py-4">
          
          {/* Elegant Header - Minimal & Clean */}
          <div className="flex items-center justify-between pb-4 border-b border-gray-200 dark:border-gray-700 mb-6">
            {/* Left: Title */}
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 bg-gradient-to-br from-red-500 to-orange-600 rounded-lg flex items-center justify-center">
                <Bot className="h-3.5 w-3.5 text-white" />
              </div>
              <h1 className="text-xl font-semibold text-gray-800 dark:text-white">
                AI Policy & Insight Generator
              </h1>
            </div>
            
            {/* Right: Controls */}
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <UserMenu />
            </div>
          </div>

        {/* Chat Messages Area - Claude-style clean & spacious */}
        <div 
          className="flex-1 overflow-y-auto mb-6"
          style={{ minHeight: 0 }}
        >
          <div className="space-y-8 py-4">
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
              </div>
              <div ref={messagesEndRef} />
            </div>

          {/* Input Area - Claude-style elegant */}
          <div className="flex-shrink-0 border-t border-gray-200 dark:border-gray-700 pt-4">
            <div className="relative">
              <textarea
                ref={textareaRef}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Reply..."
                className="w-full px-4 py-3 pr-12 border border-gray-300 dark:border-gray-600 rounded-2xl focus:outline-none focus:ring-2 focus:ring-orange-500 dark:focus:ring-orange-400 bg-white dark:bg-gray-800 text-gray-900 dark:text-white resize-none transition-all duration-200"
                style={{ minHeight: '52px', maxHeight: '150px' }}
                disabled={isLoading}
                rows={1}
              />
              <button
                onClick={handleSendMessage}
                disabled={isLoading || !inputMessage.trim()}
                className="absolute right-2 bottom-2 p-2.5 bg-gradient-to-r from-red-500 to-orange-600 hover:from-red-600 hover:to-orange-700 text-white rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                title={isLoading ? "Analyzing..." : "Send message"}
              >
                {isLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Send className="h-5 w-5" />
                )}
              </button>
            </div>
            
            {/* AI Disclaimer - Claude-style */}
            <p className="text-xs text-gray-500 dark:text-gray-400 text-center mt-3">
              AI Policy & Insight Generator can make mistakes. Please verify important information.
            </p>
          </div>
        </div>
      </div>

        {/* Compact Status Bar */}
        <div className="mt-2 text-center text-xs text-gray-500 dark:text-gray-400">
          <div className="flex items-center justify-center gap-3">
            <div className="flex items-center gap-1">
              <Database className="h-2.5 w-2.5" />
              <span className={scrapingStatus === 'in_progress' ? 'text-orange-600 dark:text-orange-400' : ''}>
                {scrapingStatus === 'in_progress' ? 'Gathering data...' : 'Data ready'}
              </span>
            </div>
            <span>•</span>
            <div className="flex items-center gap-1">
              <div className={`w-1.5 h-1.5 rounded-full ${isBackendAvailable ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className={isBackendAvailable ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                {isBackendAvailable ? 'Connected' : 'Offline'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
    </div>
  );
};

export default ChatInterface;