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

  // Load chat history on initialization
  useEffect(() => {
    loadChatHistory();
  }, []);

  const loadChatHistory = async () => {
    try {
      // Note: Kita tidak set isLoading(true) global di sini agar tidak memblokir UI utama
      // saat sidebar sedang memuat list history.
      const chatSessions = await apiService.getSessions();
      
      // FIX: Normalisasi ID menjadi String untuk konsistensi dengan URL
      const normalizedSessions = chatSessions.map(s => ({
        ...s,
        id: String(s.id)
      }));
      
      setSessions(normalizedSessions);
      
      // PERBAIKAN PENTING:
      // Jangan panggil createNewChat() di sini! 
      // Biarkan Router (ChatInterface) yang menentukan apakah harus load sesi tertentu atau buat baru.
      // Jika dipaksa createNewChat(), ini akan menimpa proses switchToSession yang sedang berjalan.
      
    } catch (error) {
      console.error('Failed to load chat history:', error);
    }
  };

  const createNewChat = () => {
    // Reset state loading agar tidak nyangkut
    setIsLoading(false);
    
    const newSession: ChatSession = {
      id: '',
      title: 'Analisis Sensus Baru',
      messages: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      metadata: {}
    };
    
    setCurrentSession(newSession);
  };

  const switchToSession = async (sessionId: string) => {
    try {
      setIsLoading(true);
      
      // Optimistic Update: Cek apakah sesi sudah ada di list sessions
      // Gunakan String() untuk perbandingan yang aman (Number vs String)
      const existingSession = sessions.find(s => String(s.id) === String(sessionId));
      
      if (existingSession && existingSession.messages && existingSession.messages.length > 0) {
         // Jika ada di cache, tampilkan dulu agar cepat
         setCurrentSession(existingSession);
      }

      // Fetch fresh data from API
      const session = await apiService.getSession(sessionId);
      
      // FIX: Paksa konversi ID ke String agar cocok dengan URL params
      const normalizedSession = {
        ...session,
        id: String(session.id)
      };

      setCurrentSession(normalizedSession);
    } catch (error) {
      console.error('Failed to switch to session:', error);
      // Jangan reset ke createNewChat() di sini, biarkan UI menangani error state
    } finally {
      setIsLoading(false);
    }
  };

  const addMessageToCurrentSession = (message: ChatMessage) => {
    if (currentSession) {
      setCurrentSession(prevSession => {
        if (!prevSession) return prevSession;
        
        const updatedSession = {
          ...prevSession,
          messages: [...prevSession.messages, message],
          updated_at: new Date().toISOString()
        };
        
        // Update session ID if it was empty (new session)
        if (!prevSession.id && message.session_id) {
          updatedSession.id = String(message.session_id); // FIX: Ensure String
          updatedSession.title = generateSessionTitle(message.content);
        }
        
        return updatedSession;
      });
      
      // Update sessions list (Sidebar) secara real-time
      setSessions(prevSessions => {
        const sessionId = currentSession.id 
          ? String(currentSession.id) 
          : (message.session_id ? String(message.session_id) : '');
          
        if (!sessionId) return prevSessions;
        
        const existingIndex = prevSessions.findIndex(s => String(s.id) === sessionId);
        
        const updatedSessionForList = {
          ...currentSession,
          id: sessionId,
          messages: [...currentSession.messages, message],
          updated_at: new Date().toISOString()
        };
        
        if (!currentSession.id && message.session_id) {
          updatedSessionForList.title = generateSessionTitle(message.content);
        }
        
        if (existingIndex >= 0) {
          const newSessions = [...prevSessions];
          newSessions[existingIndex] = updatedSessionForList;
          return newSessions;
        } else {
          return [updatedSessionForList, ...prevSessions];
        }
      });
    }
  };

  const updateMessageInCurrentSession = (messageId: string, newContent: string) => {
    if (currentSession) {
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
        if (!currentSession.id) return prevSessions;
        
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
    }
  };

  const generateSessionTitle = (firstMessage: string): string => {
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

  const deleteSession = async (sessionId: string) => {
    try {
      await apiService.deleteSession(sessionId);
      
      // Update state lokal
      setSessions(prev => prev.filter(s => String(s.id) !== String(sessionId)));
      
      // Jika sesi yang dihapus adalah sesi aktif, reset ke new chat
      if (currentSession && String(currentSession.id) === String(sessionId)) {
        createNewChat();
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
      throw error;
    }
  };

  const deleteMultipleSessions = async (sessionIds: string[]) => {
    try {
      await apiService.deleteSessions(sessionIds);
      
      const stringIds = sessionIds.map(id => String(id));
      setSessions(prev => prev.filter(s => !stringIds.includes(String(s.id))));
      
      if (currentSession && stringIds.includes(String(currentSession.id))) {
        createNewChat();
      }
    } catch (error) {
      console.error('Failed to delete sessions:', error);
      throw error;
    }
  };

  const deleteAllSessions = async () => {
    try {
      await apiService.deleteAllSessions();
      setSessions([]);
      createNewChat();
    } catch (error) {
      console.error('Failed to delete all sessions:', error);
      throw error;
    }
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