import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Mic, Plus, History, Download, Settings, TrendingUp, Lightbulb, FileText, ChevronRight, X, Loader2 } from 'lucide-react';
import api from '../services/api';
import { PolicyAnalysisRequest, PolicyAnalysisResponse, ChatSession, ChatMessage } from '../types/chat';
import DataVisualization from './DataVisualization';
import InsightsPanel from './InsightsPanel';
import PolicyPanel from './PolicyPanel';
import ReportModal from './ReportModal';

// Interface untuk message dengan data terkait
interface ChatMessageWithData {
  id: string;
  sender: 'user' | 'ai';
  content: string;
  timestamp: Date;
  // Data spesifik untuk message ini (hanya untuk AI responses)
  visualizations?: any[];
  insights?: string[];
  policies?: any[];
}

interface ExpandedSection {
  messageId: string;
  section: 'visualizations' | 'insights' | 'policies' | 'report';
}

const ChatInterface: React.FC = () => {
  // Session state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  
  // Messages state - setiap message punya data sendiri
  const [messages, setMessages] = useState<ChatMessageWithData[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // Expanded section state - track which message's section is expanded
  const [expandedSection, setExpandedSection] = useState<ExpandedSection | null>(null);
  
  // Report modal state
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportMessageId, setReportMessageId] = useState<string | null>(null);
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const response = await api.get('/sessions');
      setSessions(response.data);
    } catch (error) {
      console.error('Error loading sessions:', error);
    }
  };

  const loadSession = async (id: string) => {
    try {
      const response = await api.get(`/sessions/${id}`);
      const session: ChatSession = response.data;
      setSessionId(id);
      
      // Convert session messages to ChatMessageWithData format
      const convertedMessages: ChatMessageWithData[] = session.messages.map((msg: ChatMessage) => ({
        id: msg.id,
        sender: msg.sender,
        content: msg.content,
        timestamp: new Date(msg.timestamp),
        // Attach data only to AI messages
        visualizations: msg.sender === 'ai' ? msg.visualizations || [] : undefined,
        insights: msg.sender === 'ai' ? msg.insights || [] : undefined,
        policies: msg.sender === 'ai' ? msg.policies || [] : undefined,
      }));
      
      setMessages(convertedMessages);
      setShowHistory(false);
      
      // Reset expanded section when loading new session
      setExpandedSection(null);
    } catch (error) {
      console.error('Error loading session:', error);
    }
  };

  const startNewChat = () => {
    setSessionId(null);
    setMessages([]);
    setExpandedSection(null);
    setShowHistory(false);
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: ChatMessageWithData = {
      id: `user_${Date.now()}`,
      sender: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    // Add user message
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    
    // Reset expanded section for new conversation turn
    setExpandedSection(null);

    try {
      const request: PolicyAnalysisRequest = {
        message: userMessage.content,
        session_id: sessionId || undefined,
        include_visualizations: true,
        include_insights: true,
        include_policies: true,
      };

      const response = await api.post('/chat', request, {
        timeout: 120000, // 2 minutes for AI analysis
      });
      
      const data: PolicyAnalysisResponse = response.data;

      // Update session ID if new
      if (!sessionId && data.session_id) {
        setSessionId(data.session_id);
      }

      // Create AI message with its own data
      const aiMessage: ChatMessageWithData = {
        id: `ai_${Date.now()}`,
        sender: 'ai',
        content: data.message,
        timestamp: new Date(),
        // Attach response data to THIS specific message
        visualizations: data.visualizations || [],
        insights: data.insights || [],
        policies: data.policies || [],
      };

      setMessages(prev => [...prev, aiMessage]);

    } catch (error) {
      console.error('Error sending message:', error);
      
      const errorMessage: ChatMessageWithData = {
        id: `error_${Date.now()}`,
        sender: 'ai',
        content: 'Maaf, terjadi kesalahan saat memproses pesan Anda. Silakan coba lagi.',
        timestamp: new Date(),
        visualizations: [],
        insights: [],
        policies: [],
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const toggleSection = (messageId: string, section: ExpandedSection['section']) => {
    if (expandedSection?.messageId === messageId && expandedSection?.section === section) {
      setExpandedSection(null);
    } else {
      setExpandedSection({ messageId, section });
    }
  };

  const openReportModal = (messageId: string) => {
    setReportMessageId(messageId);
    setShowReportModal(true);
  };

  // Get data for currently expanded section
  const getExpandedData = useCallback(() => {
    if (!expandedSection) return null;
    
    const message = messages.find(m => m.id === expandedSection.messageId);
    if (!message || message.sender !== 'ai') return null;
    
    return {
      visualizations: message.visualizations || [],
      insights: message.insights || [],
      policies: message.policies || [],
    };
  }, [expandedSection, messages]);

  // Render action buttons for AI message
  const renderMessageActions = (message: ChatMessageWithData) => {
    if (message.sender !== 'ai') return null;
    
    const vizCount = message.visualizations?.length || 0;
    const insightCount = message.insights?.length || 0;
    const policyCount = message.policies?.length || 0;
    
    // Don't show action buttons if no data
    if (vizCount === 0 && insightCount === 0 && policyCount === 0) {
      return null;
    }

    const isExpanded = (section: ExpandedSection['section']) => 
      expandedSection?.messageId === message.id && expandedSection?.section === section;

    return (
      <div className="mt-3 space-y-2">
        {/* Visualizations Button */}
        {vizCount > 0 && (
          <button
            onClick={() => toggleSection(message.id, 'visualizations')}
            className={`w-full flex items-center justify-between p-3 rounded-lg transition-all ${
              isExpanded('visualizations') 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-700 hover:bg-gray-600 text-gray-200'
            }`}
          >
            <div className="flex items-center gap-3">
              <TrendingUp className="w-5 h-5" />
              <div className="text-left">
                <div className="font-medium">Data Visualizations</div>
                <div className="text-sm opacity-75">{vizCount} charts</div>
              </div>
            </div>
            <ChevronRight className={`w-5 h-5 transition-transform ${isExpanded('visualizations') ? 'rotate-90' : ''}`} />
          </button>
        )}

        {/* Insights Button */}
        {insightCount > 0 && (
          <button
            onClick={() => toggleSection(message.id, 'insights')}
            className={`w-full flex items-center justify-between p-3 rounded-lg transition-all ${
              isExpanded('insights') 
                ? 'bg-yellow-600 text-white' 
                : 'bg-gray-700 hover:bg-gray-600 text-gray-200'
            }`}
          >
            <div className="flex items-center gap-3">
              <Lightbulb className="w-5 h-5" />
              <div className="text-left">
                <div className="font-medium">Key Insights</div>
                <div className="text-sm opacity-75">{insightCount} insights</div>
              </div>
            </div>
            <ChevronRight className={`w-5 h-5 transition-transform ${isExpanded('insights') ? 'rotate-90' : ''}`} />
          </button>
        )}

        {/* Policies Button */}
        {policyCount > 0 && (
          <button
            onClick={() => toggleSection(message.id, 'policies')}
            className={`w-full flex items-center justify-between p-3 rounded-lg transition-all ${
              isExpanded('policies') 
                ? 'bg-orange-600 text-white' 
                : 'bg-gray-700 hover:bg-gray-600 text-gray-200'
            }`}
          >
            <div className="flex items-center gap-3">
              <FileText className="w-5 h-5" />
              <div className="text-left">
                <div className="font-medium">Policy Recommendations</div>
                <div className="text-sm opacity-75">{policyCount} recommendations</div>
              </div>
            </div>
            <ChevronRight className={`w-5 h-5 transition-transform ${isExpanded('policies') ? 'rotate-90' : ''}`} />
          </button>
        )}

        {/* Download Report Button - only if has any data */}
        <button
          onClick={() => openReportModal(message.id)}
          className="w-full flex items-center justify-between p-3 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 transition-all"
        >
          <div className="flex items-center gap-3">
            <Download className="w-5 h-5" />
            <div className="text-left">
              <div className="font-medium">Unduh Laporan Lengkap</div>
              <div className="text-sm opacity-75">1 report</div>
            </div>
          </div>
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>
    );
  };

  // Render expanded panel
  const renderExpandedPanel = () => {
    if (!expandedSection) return null;
    
    const data = getExpandedData();
    if (!data) return null;

    return (
      <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
        <div className="bg-gray-800 rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-700">
            <h2 className="text-xl font-bold text-white">
              {expandedSection.section === 'visualizations' && 'Data Visualizations'}
              {expandedSection.section === 'insights' && 'Key Insights'}
              {expandedSection.section === 'policies' && 'Policy Recommendations'}
            </h2>
            <button
              onClick={() => setExpandedSection(null)}
              className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>
          
          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4">
            {expandedSection.section === 'visualizations' && (
              <DataVisualization visualizations={data.visualizations} />
            )}
            {expandedSection.section === 'insights' && (
              <InsightsPanel insights={data.insights} />
            )}
            {expandedSection.section === 'policies' && (
              <PolicyPanel policies={data.policies} />
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-screen bg-gray-900">
      {/* Sidebar */}
      <div className="w-16 bg-gray-800 flex flex-col items-center py-4 gap-4">
        <button
          onClick={startNewChat}
          className="p-3 rounded-xl bg-orange-600 hover:bg-orange-500 transition-colors"
          title="New Chat"
        >
          <Plus className="w-5 h-5 text-white" />
        </button>
        
        <button
          onClick={() => setShowHistory(!showHistory)}
          className={`p-3 rounded-xl transition-colors ${showHistory ? 'bg-gray-600' : 'hover:bg-gray-700'}`}
          title="History"
        >
          <History className="w-5 h-5 text-gray-300" />
        </button>
        
        <button
          className="p-3 rounded-xl hover:bg-gray-700 transition-colors"
          title="Downloads"
        >
          <Download className="w-5 h-5 text-gray-300" />
        </button>
        
        <div className="flex-1" />
        
        <button
          className="p-3 rounded-xl hover:bg-gray-700 transition-colors"
          title="Settings"
        >
          <Settings className="w-5 h-5 text-gray-300" />
        </button>
      </div>

      {/* History Panel */}
      {showHistory && (
        <div className="w-64 bg-gray-800 border-r border-gray-700 overflow-y-auto">
          <div className="p-4">
            <h3 className="text-lg font-semibold text-white mb-4">Chat History</h3>
            {sessions.length === 0 ? (
              <p className="text-gray-400 text-sm">No previous chats</p>
            ) : (
              <div className="space-y-2">
                {sessions.map(session => (
                  <button
                    key={session.id}
                    onClick={() => loadSession(session.id)}
                    className={`w-full text-left p-3 rounded-lg transition-colors ${
                      sessionId === session.id ? 'bg-gray-600' : 'hover:bg-gray-700'
                    }`}
                  >
                    <div className="text-white text-sm font-medium truncate">
                      {session.title}
                    </div>
                    <div className="text-gray-400 text-xs">
                      {new Date(session.updated_at).toLocaleDateString()}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="h-16 bg-gray-800 border-b border-gray-700 flex items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-orange-600 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-white" />
            </div>
            <h1 className="text-lg font-semibold text-white">AI Policy & Insight Generator</h1>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center">
                <div className="w-16 h-16 rounded-full bg-orange-600/20 flex items-center justify-center mx-auto mb-4">
                  <TrendingUp className="w-8 h-8 text-orange-500" />
                </div>
                <h2 className="text-xl font-semibold text-white mb-2">
                  Selamat Datang!
                </h2>
                <p className="text-gray-400 max-w-md">
                  Tanyakan apa saja tentang data Sensus Ekonomi Indonesia. 
                  Saya dapat membantu menganalisis jumlah usaha per provinsi, sektor, dan memberikan insight kebijakan.
                </p>
              </div>
            </div>
          ) : (
            messages.map(message => (
              <div
                key={message.id}
                className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-3xl rounded-2xl p-4 ${
                    message.sender === 'user'
                      ? 'bg-orange-600 text-white'
                      : 'bg-gray-800 text-gray-100'
                  }`}
                >
                  {/* Message Content */}
                  <div className="whitespace-pre-wrap">{message.content}</div>
                  
                  {/* Timestamp */}
                  <div className={`text-xs mt-2 ${message.sender === 'user' ? 'text-orange-200' : 'text-gray-500'}`}>
                    {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                  
                  {/* Action Buttons - Only for AI messages with data */}
                  {renderMessageActions(message)}
                </div>
              </div>
            ))
          )}
          
          {/* Loading indicator */}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 rounded-2xl p-4 flex items-center gap-3">
                <Loader2 className="w-5 h-5 text-orange-500 animate-spin" />
                <span className="text-gray-300">Menganalisis data...</span>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-gray-700">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-end gap-3 bg-gray-800 rounded-xl p-3">
              <button className="p-2 hover:bg-gray-700 rounded-lg transition-colors">
                <Mic className="w-5 h-5 text-gray-400" />
              </button>
              
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Reply..."
                className="flex-1 bg-transparent text-white placeholder-gray-500 resize-none outline-none min-h-[24px] max-h-32"
                rows={1}
              />
              
              <button
                onClick={sendMessage}
                disabled={!inputValue.trim() || isLoading}
                className="p-2 bg-orange-600 hover:bg-orange-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                <Send className="w-5 h-5 text-white" />
              </button>
            </div>
            
            <div className="text-center mt-2">
              <span className="text-xs text-gray-500">
                📊 Data ready • <span className="text-green-500">● Connected</span>
              </span>
              <br />
              <span className="text-xs text-gray-600">AI can make mistakes. Verify info.</span>
            </div>
          </div>
        </div>
      </div>

      {/* Expanded Panel Modal */}
      {renderExpandedPanel()}

      {/* Report Modal */}
      {showReportModal && sessionId && (
        <ReportModal
          isOpen={showReportModal}
          sessionId={sessionId}
          onClose={() => {
            setShowReportModal(false);
            setReportMessageId(null);
          }}
          // Pass the specific message's data to report modal
          message={messages.find(m => m.id === reportMessageId) as any}
        />
      )}
    </div>
  );
};

export default ChatInterface;