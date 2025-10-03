import React, { useState } from 'react';
import { 
  Plus, 
  MessageSquare, 
  Download, 
  History, 
  Calendar,
  FileText,
  ChevronLeft,
  Trash2,
  MoreHorizontal
} from 'lucide-react';
import { useChat } from '../contexts/ChatContext';
import { format } from 'date-fns';
import BrandLogo from './BrandLogo';

interface ChatSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

const ChatSidebar: React.FC<ChatSidebarProps> = ({ isOpen, onToggle }) => {
  const { 
    currentSession, 
    sessions, 
    isLoading, 
    createNewChat, 
    switchToSession, 
    exportCurrentChat, 
    exportAllChats 
  } = useChat();

  const [showExportMenu, setShowExportMenu] = useState(false);

  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), 'MMM dd, HH:mm');
    } catch {
      return 'Unknown date';
    }
  };

  const getMessageCount = (session: any) => {
    return session.messages?.length || 0;
  };

  return (
    <>
      {/* Sidebar */}
      <div className={`fixed left-0 top-0 h-full bg-white dark:bg-gray-800 border-r border-orange-200 dark:border-gray-700 shadow-lg transform transition-transform duration-300 z-40 ${
        isOpen ? 'translate-x-0' : '-translate-x-full'
      } w-80`}>
        
        {/* Header */}
        <div className="p-4 border-b border-orange-200 dark:border-gray-700">
          {/* Brand Section */}
          <div className="flex items-center justify-between mb-4">
            <BrandLogo size="lg" showText={true} />
            <button
              onClick={onToggle}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors duration-200"
              aria-label="Close sidebar"
            >
              <ChevronLeft className="h-5 w-5 text-gray-600 dark:text-gray-300" />
            </button>
          </div>
          
          {/* Chat History Title */}
          <div className="flex items-center gap-2 mb-4">
            <History className="h-4 w-4 text-orange-600" />
            <h2 className="text-base font-medium text-gray-800 dark:text-white">Chat History</h2>
          </div>

          {/* Action Buttons */}
          <div className="space-y-2">
            <button
              onClick={createNewChat}
              className="w-full flex items-center gap-3 px-3 py-2 bg-gradient-to-r from-red-500 to-orange-600 hover:from-red-600 hover:to-orange-700 text-white rounded-lg transition-all duration-200 font-medium"
            >
              <Plus className="h-4 w-4" />
              New Chat
            </button>

            <div className="relative">
              <button
                onClick={() => setShowExportMenu(!showExportMenu)}
                className="w-full flex items-center gap-3 px-3 py-2 border border-orange-200 dark:border-gray-600 hover:bg-orange-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg transition-all duration-200"
              >
                <Download className="h-4 w-4" />
                Export Chats
                <MoreHorizontal className="h-4 w-4 ml-auto" />
              </button>

              {showExportMenu && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-700 border border-orange-200 dark:border-gray-600 rounded-lg shadow-lg z-50">
                  <button
                    onClick={() => {
                      exportCurrentChat();
                      setShowExportMenu(false);
                    }}
                    className="w-full text-left px-3 py-2 hover:bg-orange-50 dark:hover:bg-gray-600 text-sm text-gray-700 dark:text-gray-200 flex items-center gap-2"
                  >
                    <FileText className="h-4 w-4" />
                    Current Chat
                  </button>
                  <button
                    onClick={() => {
                      exportAllChats();
                      setShowExportMenu(false);
                    }}
                    className="w-full text-left px-3 py-2 hover:bg-orange-50 dark:hover:bg-gray-600 text-sm text-gray-700 dark:text-gray-200 flex items-center gap-2 border-t border-gray-200 dark:border-gray-600"
                  >
                    <Download className="h-4 w-4" />
                    All Chats
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Chat Sessions List */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-300">
              <MessageSquare className="h-12 w-12 mx-auto mb-3 text-gray-300 dark:text-gray-500" />
              <p>No chat history yet</p>
              <p className="text-sm">Start a new conversation!</p>
            </div>
          ) : (
            <div className="space-y-2">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => switchToSession(session.id)}
                  className={`p-3 rounded-lg cursor-pointer transition-all duration-200 border ${
                    currentSession?.id === session.id
                      ? 'bg-orange-50 dark:bg-gray-700 border-orange-200 dark:border-gray-600'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-700 border-transparent'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-gray-800 dark:text-gray-100 truncate">
                        {session.title || 'Untitled Chat'}
                      </h3>
                      <div className="flex items-center gap-2 mt-1 text-xs text-gray-500 dark:text-gray-300">
                        <Calendar className="h-3 w-3" />
                        <span>{formatDate(session.created_at)}</span>
                        <span>•</span>
                        <span>{getMessageCount(session)} messages</span>
                      </div>
                    </div>
                    {currentSession?.id === session.id && (
                      <div className="w-2 h-2 bg-orange-600 rounded-full flex-shrink-0 ml-2 mt-2"></div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer Stats */}
        <div className="p-4 border-t border-orange-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <div className="text-xs text-gray-600 dark:text-gray-300 space-y-1">
            <div className="flex justify-between">
              <span>Total Sessions:</span>
              <span className="font-medium">{sessions.length}</span>
            </div>
            <div className="flex justify-between">
              <span>Current Session:</span>
              <span className="font-medium">{currentSession ? getMessageCount(currentSession) : 0} messages</span>
            </div>
          </div>
        </div>
      </div>

      {/* Note: Toggle button now handled by separate SidebarToggle component */}

      {/* Overlay (when sidebar is open) */}
      {isOpen && (
        <div
          onClick={onToggle}
          className="fixed inset-0 bg-black bg-opacity-25 z-30"
        />
      )}
    </>
  );
};

export default ChatSidebar;