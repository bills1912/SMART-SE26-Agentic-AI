import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Database } from 'lucide-react';
import { ChatMessage } from '../types/chat';
import MessageBubble from './MessageBubble';
import { toast } from '../hooks/use-toast';
import apiService from '../services/api';
import ThemeToggle from './ThemeToggle';
import ChatSidebar from './ChatSidebar';
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
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Math.random().toString(36).substr(2, 9),
      session_id: currentSessionId || 'temp',
      sender: 'user',
      content: inputMessage.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    const originalMessage = inputMessage.trim();
    setInputMessage('');
    setIsLoading(true);

    try {
      if (!isBackendAvailable) {
        throw new Error('Backend service is currently unavailable');
      }

      // Call real API
      const response = await apiService.sendMessage(originalMessage, currentSessionId || undefined);
      
      // Update session ID if this is a new conversation
      if (!currentSessionId) {
        setCurrentSessionId(response.session_id);
      }
      
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
      
      setMessages(prev => [...prev, aiResponse]);
      
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
        session_id: currentSessionId || 'temp',
        sender: 'ai',
        content: 'I apologize, but I encountered an issue while analyzing your policy question. This could be due to high demand or temporary service issues. Please try again in a moment.',
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, errorResponse]);
      
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
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-white to-red-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 p-4 transition-colors duration-300">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6 text-center relative">
          {/* Theme Toggle - Top Right */}
          <div className="absolute top-0 right-0">
            <ThemeToggle />
          </div>
          
          <div className="inline-flex items-center gap-3 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-2xl px-6 py-4 shadow-lg border border-orange-200 dark:border-gray-700">
            <div className="w-12 h-12 bg-gradient-to-br from-red-500 to-orange-600 rounded-xl flex items-center justify-center">
              <Bot className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-red-600 to-orange-600 bg-clip-text text-transparent">
                AI Policy & Insight Generator
              </h1>
              <p className="text-gray-600 dark:text-gray-300 text-sm">Advanced policy analysis with interactive visualizations</p>
            </div>
          </div>
        </div>

        {/* Chat Area */}
        <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm border-orange-200 dark:border-gray-700 shadow-xl rounded-xl border">
          <div className="h-[70vh] flex flex-col">
            {/* Messages */}
            <div className="flex-1 p-6 overflow-auto">
              <div className="space-y-4">
                {messages.map((message) => (
                  <MessageBubble key={message.id} message={message} />
                ))}
                {isLoading && (
                  <div className="flex items-center gap-3 p-4">
                    <div className="w-8 h-8 bg-gradient-to-br from-red-500 to-orange-600 rounded-full flex items-center justify-center">
                      <Bot className="h-4 w-4 text-white" />
                    </div>
                    <div className="flex items-center gap-2 text-gray-600 dark:text-gray-300">
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

            {/* Input Area */}
            <div className="border-t border-orange-200 dark:border-gray-700 p-6">
              <div className="flex gap-4">
                <div className="flex-1">
                  <textarea
                    ref={textareaRef}
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Describe your policy scenario or ask for analysis..."
                    className="min-h-[80px] w-full resize-none border border-orange-200 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-md p-3 focus:border-red-400 focus:ring-1 focus:ring-red-400/20 focus:outline-none"
                    disabled={isLoading}
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <button
                    onClick={handleSendMessage}
                    disabled={!inputMessage.trim() || isLoading}
                    className="h-full px-4 py-2 bg-gradient-to-r from-red-500 to-orange-600 hover:from-red-600 hover:to-orange-700 text-white shadow-lg transform transition-all duration-200 hover:scale-105 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isLoading ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <Send className="h-5 w-5" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Status Bar */}
        <div className="mt-4 text-center text-sm text-gray-500 dark:text-gray-400">
          <div className="flex items-center justify-center gap-4">
            <span>AI-powered policy analysis</span>
            <span>•</span>
            <span>Real-time visualizations</span>
            <span>•</span>
            <div className="flex items-center gap-1">
              <Database className="h-3 w-3" />
              <span className={scrapingStatus === 'in_progress' ? 'text-orange-600 dark:text-orange-400' : 'text-gray-500 dark:text-gray-400'}>
                {scrapingStatus === 'in_progress' ? 'Gathering data...' : 'Data ready'}
              </span>
            </div>
            <span>•</span>
            <div className={`w-2 h-2 rounded-full ${isBackendAvailable ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className={isBackendAvailable ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
              {isBackendAvailable ? 'Connected' : 'Offline'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;