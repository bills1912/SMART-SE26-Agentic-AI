import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { ChatSession, ChatMessage } from '../types/chat';
import apiService from '../services/api';

interface ChatContextType {
  currentSession: ChatSession | null;
  sessions: ChatSession[];
  isLoading: boolean;
  createNewChat: () => void;
  switchToSession: (sessionId: string) => Promise<void>;
  exportCurrentChat: () => void;
  exportAllChats: () => void;
  loadChatHistory: () => Promise<void>;
  addMessageToCurrentSession: (message: ChatMessage) => void;
  updateMessageInCurrentSession: (messageId: string, newContent: string) => void;
  deleteSession: (sessionId: string) => Promise<void>;
  deleteMultipleSessions: (sessionIds: string[]) => Promise<void>;
  deleteAllSessions: () => Promise<void>;
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
  
  // Ref to track if we're currently switching sessions
  const switchingRef = useRef(false);
  const loadingHistoryRef = useRef(false);

  // Load chat history on initialization
  useEffect(() => {
    loadChatHistory();
  }, []);

  const loadChatHistory = useCallback(async () => {
    // Prevent duplicate loading
    if (loadingHistoryRef.current) {
      console.log('[ChatContext] Already loading history, skipping');
      return;
    }
    
    loadingHistoryRef.current = true;
    
    try {
      console.log('[ChatContext] Loading chat history...');
      const chatSessions = await apiService.getSessions();
      
      // Normalize IDs to String for consistency
      const normalizedSessions = chatSessions.map(s => ({
        ...s,
        id: String(s.id)
      }));
      
      setSessions(normalizedSessions);
      console.log(`[ChatContext] Loaded ${normalizedSessions.length} sessions`);
      
    } catch (error) {
      console.error('[ChatContext] Failed to load chat history:', error);
    } finally {
      loadingHistoryRef.current = false;
    }
  }, []);

  const createNewChat = useCallback(() => {
    console.log('[ChatContext] Creating new chat');
    
    // Reset loading state
    setIsLoading(false);
    switchingRef.current = false;
    
    const newSession: ChatSession = {
      id: '',
      title: 'Analisis Sensus Baru',
      messages: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      metadata: {}
    };
    
    setCurrentSession(newSession);
  }, []);

  const switchToSession = useCallback(async (sessionId: string): Promise<void> => {
    // Prevent concurrent switches
    if (switchingRef.current) {
      console.log('[ChatContext] Switch already in progress, queueing...');
      // Wait a bit and retry
      await new Promise(resolve => setTimeout(resolve, 100));
      if (switchingRef.current) {
        console.log('[ChatContext] Still switching, aborting');
        return;
      }
    }
    
    const normalizedId = String(sessionId);
    
    // Check if already on this session
    if (currentSession && String(currentSession.id) === normalizedId) {
      console.log('[ChatContext] Already on session:', normalizedId);
      return;
    }
    
    console.log(`[ChatContext] Switching to session: ${normalizedId}`);
    switchingRef.current = true;
    setIsLoading(true);
    
    try {
      // Optimistic update: Check if session exists in cache
      const cachedSession = sessions.find(s => String(s.id) === normalizedId);
      
      if (cachedSession && cachedSession.messages && cachedSession.messages.length > 0) {
        console.log('[ChatContext] Using cached session data');
        setCurrentSession({
          ...cachedSession,
          id: normalizedId
        });
      }

      // Fetch fresh data from API
      console.log('[ChatContext] Fetching session from API...');
      const session = await apiService.getSession(sessionId);
      
      // Normalize the session ID
      const normalizedSession: ChatSession = {
        ...session,
        id: String(session.id)
      };

      console.log(`[ChatContext] Session loaded with ${normalizedSession.messages?.length || 0} messages`);
      setCurrentSession(normalizedSession);
      
    } catch (error) {
      console.error('[ChatContext] Failed to switch to session:', error);
      throw error;
    } finally {
      setIsLoading(false);
      switchingRef.current = false;
    }
  }, [currentSession, sessions]);

  const addMessageToCurrentSession = useCallback((message: ChatMessage) => {
    setCurrentSession(prevSession => {
      if (!prevSession) {
        console.warn('[ChatContext] No current session to add message to');
        return prevSession;
      }
      
      const updatedSession: ChatSession = {
        ...prevSession,
        messages: [...prevSession.messages, message],
        updated_at: new Date().toISOString()
      };
      
      // Update session ID if it was empty (new session)
      if (!prevSession.id && message.session_id) {
        updatedSession.id = String(message.session_id);
        updatedSession.title = generateSessionTitle(message.content);
      }
      
      return updatedSession;
    });
    
    // Update sessions list (Sidebar)
    setSessions(prevSessions => {
      const sessionId = currentSession?.id 
        ? String(currentSession.id) 
        : (message.session_id ? String(message.session_id) : '');
        
      if (!sessionId) return prevSessions;
      
      const existingIndex = prevSessions.findIndex(s => String(s.id) === sessionId);
      
      const currentMessages = currentSession?.messages || [];
      const updatedSessionForList: ChatSession = {
        id: sessionId,
        title: currentSession?.title || generateSessionTitle(message.content),
        messages: [...currentMessages, message],
        created_at: currentSession?.created_at || new Date().toISOString(),
        updated_at: new Date().toISOString(),
        metadata: currentSession?.metadata || {}
      };
      
      if (existingIndex >= 0) {
        const newSessions = [...prevSessions];
        newSessions[existingIndex] = updatedSessionForList;
        return newSessions;
      } else {
        return [updatedSessionForList, ...prevSessions];
      }
    });
  }, [currentSession]);

  const updateMessageInCurrentSession = useCallback((messageId: string, newContent: string) => {
    setCurrentSession(prevSession => {
      if (!prevSession) return prevSession;
      
      const updatedMessages = prevSession.messages.map(msg => 
        msg.id === messageId 
          ? { ...msg, content: newContent, timestamp: new Date() }
          : msg
      );
      
      return {
        ...prevSession,
        messages: updatedMessages,
        updated_at: new Date().toISOString()
      };
    });

    // Also update in sessions list
    setSessions(prevSessions => {
      if (!currentSession?.id) return prevSessions;
      
      return prevSessions.map(session => {
        if (String(session.id) === String(currentSession.id)) {
          return {
            ...session,
            messages: session.messages.map(msg =>
              msg.id === messageId
                ? { ...msg, content: newContent, timestamp: new Date() }
                : msg
            ),
            updated_at: new Date().toISOString()
          };
        }
        return session;
      });
    });
  }, [currentSession]);

  const generateSessionTitle = (firstMessage: string): string => {
    const words = firstMessage.split(' ').slice(0, 6).join(' ');
    return words.length > 50 ? words.substring(0, 47) + '...' : words;
  };

  const exportCurrentChat = useCallback(() => {
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
  }, [currentSession]);

  const exportAllChats = useCallback(() => {
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
  }, [sessions]);

  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      await apiService.deleteSession(sessionId);
      
      // Update local state
      setSessions(prev => prev.filter(s => String(s.id) !== String(sessionId)));
      
      // If deleted session is current, reset to new chat
      if (currentSession && String(currentSession.id) === String(sessionId)) {
        createNewChat();
      }
    } catch (error) {
      console.error('[ChatContext] Failed to delete session:', error);
      throw error;
    }
  }, [currentSession, createNewChat]);

  const deleteMultipleSessions = useCallback(async (sessionIds: string[]) => {
    try {
      await apiService.deleteSessions(sessionIds);
      
      const stringIds = sessionIds.map(id => String(id));
      setSessions(prev => prev.filter(s => !stringIds.includes(String(s.id))));
      
      if (currentSession && stringIds.includes(String(currentSession.id))) {
        createNewChat();
      }
    } catch (error) {
      console.error('[ChatContext] Failed to delete sessions:', error);
      throw error;
    }
  }, [currentSession, createNewChat]);

  const deleteAllSessions = useCallback(async () => {
    try {
      await apiService.deleteAllSessions();
      setSessions([]);
      createNewChat();
    } catch (error) {
      console.error('[ChatContext] Failed to delete all sessions:', error);
      throw error;
    }
  }, [createNewChat]);

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
        addMessageToCurrentSession,
        updateMessageInCurrentSession,
        deleteSession,
        deleteMultipleSessions,
        deleteAllSessions,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};