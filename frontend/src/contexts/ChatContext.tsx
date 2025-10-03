import React, { createContext, useContext, useEffect, useState } from 'react';
import { ChatSession, ChatMessage } from '../types/chat';
import apiService from '../services/api';

interface ChatContextType {
  currentSession: ChatSession | null;
  sessions: ChatSession[];
  isLoading: boolean;
  createNewChat: () => void;
  switchToSession: (sessionId: string) => void;
  exportCurrentChat: () => void;
  exportAllChats: () => void;
  loadChatHistory: () => Promise<void>;
  addMessageToCurrentSession: (message: ChatMessage) => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const useChat = () => {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};

interface ChatProviderProps {
  children: React.ReactNode;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Load chat history on initialization
  useEffect(() => {
    loadChatHistory();
  }, []);

  const loadChatHistory = async () => {
    try {
      setIsLoading(true);
      const chatSessions = await apiService.getSessions();
      setSessions(chatSessions);
      
      // If no current session, create a new one or load the most recent
      if (!currentSession && chatSessions.length > 0) {
        const latestSession = chatSessions[0];
        const fullSession = await apiService.getSession(latestSession.id);
        setCurrentSession(fullSession);
      }
    } catch (error) {
      console.error('Failed to load chat history:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const createNewChat = () => {
    // Create a new local session - it will be created on backend when first message is sent
    const newSession: ChatSession = {
      id: '',
      title: 'New Policy Analysis',
      messages: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      metadata: {}
    };
    
    setCurrentSession(newSession);
    
    // Add welcome message to new session
    const welcomeMessage: ChatMessage = {
      id: 'welcome_' + Date.now(),
      session_id: '',
      sender: 'ai',
      content: 'Hello! I\'m your AI Policy Analyst. I can help you analyze policy scenarios, generate insights, and create visualizations using real-time data from government, economic, news, and academic sources. What policy area would you like to explore today?',
      timestamp: new Date(),
    };
    
    newSession.messages = [welcomeMessage];
  };

  const switchToSession = async (sessionId: string) => {
    try {
      setIsLoading(true);
      const session = await apiService.getSession(sessionId);
      setCurrentSession(session);
    } catch (error) {
      console.error('Failed to switch to session:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const addMessageToCurrentSession = (message: ChatMessage) => {
    if (currentSession) {
      const updatedSession = {
        ...currentSession,
        messages: [...currentSession.messages, message],
        updated_at: new Date().toISOString()
      };
      
      // Update session ID if it was empty (new session)
      if (!currentSession.id && message.session_id) {
        updatedSession.id = message.session_id;
        updatedSession.title = generateSessionTitle(message.content);
      }
      
      setCurrentSession(updatedSession);
      
      // Update sessions list
      setSessions(prevSessions => {
        const existingIndex = prevSessions.findIndex(s => s.id === updatedSession.id);
        if (existingIndex >= 0) {
          const newSessions = [...prevSessions];
          newSessions[existingIndex] = updatedSession;
          return newSessions;
        } else {
          return [updatedSession, ...prevSessions];
        }
      });
    }
  };

  const generateSessionTitle = (firstMessage: string): string => {
    // Generate a title from the first user message
    const words = firstMessage.split(' ').slice(0, 6).join(' ');
    return words.length > 50 ? words.substring(0, 47) + '...' : words;
  };

  const exportCurrentChat = () => {
    if (!currentSession) return;
    
    const chatData = {
      title: currentSession.title,
      created: new Date(currentSession.created_at).toLocaleString(),
      messages: currentSession.messages.map(msg => ({
        sender: msg.sender,
        content: msg.content,
        timestamp: new Date(msg.timestamp).toLocaleString(),
        hasVisualizations: (msg.visualizations?.length || 0) > 0,
        hasInsights: (msg.insights?.length || 0) > 0,
        hasPolicies: (msg.policies?.length || 0) > 0
      }))
    };

    const blob = new Blob([JSON.stringify(chatData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `chat-${currentSession.title.replace(/[^a-zA-Z0-9]/g, '_')}-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const exportAllChats = () => {
    const allChatsData = {
      exportDate: new Date().toLocaleString(),
      totalSessions: sessions.length,
      sessions: sessions.map(session => ({
        title: session.title,
        created: new Date(session.created_at).toLocaleString(),
        messageCount: session.messages?.length || 0,
        messages: session.messages?.map(msg => ({
          sender: msg.sender,
          content: msg.content,
          timestamp: new Date(msg.timestamp).toLocaleString(),
          hasVisualizations: (msg.visualizations?.length || 0) > 0,
          hasInsights: (msg.insights?.length || 0) > 0,
          hasPolicies: (msg.policies?.length || 0) > 0
        })) || []
      }))
    };

    const blob = new Blob([JSON.stringify(allChatsData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `all-chats-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <ChatContext.Provider
      value={{
        currentSession,
        sessions,
        isLoading,
        createNewChat,
        switchToSession,
        exportCurrentChat,
        exportAllChats,
        loadChatHistory,
        addMessageToCurrentSession
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};