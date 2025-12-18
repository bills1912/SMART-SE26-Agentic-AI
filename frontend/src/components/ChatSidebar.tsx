import React, { useState } from "react";
import {
  Plus,
  MessageSquare,
  Download,
  History,
  Calendar,
  FileText,
  ChevronLeft,
  Trash2,
  MoreHorizontal,
  CheckSquare,
  Square,
  X,
  AlertTriangle
} from "lucide-react";
import { useChat } from "../contexts/ChatContext";
import { format } from "date-fns";
import BrandLogo from "./BrandLogo";
import { toast } from "../hooks/use-toast";
import DeleteConfirmationModal from "./DeleteConfirmationModal";
import { useNavigate } from "react-router-dom";

interface ChatSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  onSwitchSession?: (sessionId: string) => void;
  onNewChat?: () => void;
}

// Type for modal state
type DeleteModalState = {
  isOpen: boolean;
  type: 'single' | 'bulk' | 'all' | null;
  targetId?: string;
};

const ChatSidebar: React.FC<ChatSidebarProps> = ({ 
  isOpen, 
  onToggle,
  onSwitchSession,
  onNewChat 
}) => {
  const {
    currentSession,
    sessions,
    isLoading,
    createNewChat,
    switchToSession,
    exportCurrentChat,
    exportAllChats,
    deleteSession,
    deleteMultipleSessions,
    deleteAllSessions
  } = useChat();

  const navigate = useNavigate();

  const [showExportMenu, setShowExportMenu] = useState(false);
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedSessions, setSelectedSessions] = useState<string[]>([]);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteModal, setDeleteModal] = useState<DeleteModalState>({
    isOpen: false,
    type: null,
  });

  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), "MMM dd, HH:mm");
    } catch {
      return "Unknown date";
    }
  };

  const getMessageCount = (session: any) => {
    if (typeof session.message_count === "number") return session.message_count;
    if (!session.messages) return 0;
    return session.messages.filter((msg: any) => !msg.id?.startsWith("welcome_")).length;
  };

  const getTotalMessages = () => sessions.reduce((total, session) => total + getMessageCount(session), 0);

  // Handle session click
  const handleSessionClick = (sessionId: string) => {
    if (isSelectionMode) return;
    
    console.log(`[ChatSidebar] Session clicked: ${sessionId}`);
    
    // Use callback if provided, otherwise use context directly
    if (onSwitchSession) {
      onSwitchSession(sessionId);
    } else {
      // Fallback: navigate directly
      navigate(`/c/${sessionId}`);
    }
    
    onToggle(); // Close sidebar on mobile
  };

  // Handle new chat click
  const handleNewChatClick = () => {
    console.log('[ChatSidebar] New chat clicked');
    
    if (onNewChat) {
      onNewChat();
    } else {
      createNewChat();
      navigate('/dashboard');
    }
    
    onToggle();
  };

  // Selection logic
  const toggleSelection = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (selectedSessions.includes(sessionId)) {
      setSelectedSessions(prev => prev.filter(id => id !== sessionId));
    } else {
      setSelectedSessions(prev => [...prev, sessionId]);
    }
  };

  // Modal triggers
  const triggerBulkDelete = () => {
    if (selectedSessions.length === 0) return;
    setDeleteModal({ isOpen: true, type: 'bulk' });
  };

  const triggerSingleDelete = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteModal({ isOpen: true, type: 'single', targetId: sessionId });
    setShowExportMenu(false);
  };

  const triggerDeleteAll = () => {
    setDeleteModal({ isOpen: true, type: 'all' });
    setShowExportMenu(false);
  };

  const closeDeleteModal = () => {
    if (isDeleting) return;
    setDeleteModal({ isOpen: false, type: null, targetId: undefined });
  };

  // Execute delete
  const handleConfirmDelete = async () => {
    setIsDeleting(true);
    try {
      if (deleteModal.type === 'single' && deleteModal.targetId) {
        await deleteSession(deleteModal.targetId);
        toast({ title: "Sesi percakapan berhasil dihapus" });

      } else if (deleteModal.type === 'bulk') {
        await deleteMultipleSessions(selectedSessions);
        toast({ title: `${selectedSessions.length} sesi berhasil dihapus` });
        setIsSelectionMode(false);
        setSelectedSessions([]);

      } else if (deleteModal.type === 'all') {
        await deleteAllSessions();
        toast({ title: "Semua riwayat percakapan berhasil dihapus" });
      }
      
      // Navigate to dashboard if current session was deleted
      if (deleteModal.type === 'single' && deleteModal.targetId === currentSession?.id) {
        navigate('/dashboard');
      } else if (deleteModal.type === 'bulk' && currentSession && selectedSessions.includes(currentSession.id)) {
        navigate('/dashboard');
      } else if (deleteModal.type === 'all') {
        navigate('/dashboard');
      }
      
    } catch (error) {
      console.error("Delete failed:", error);
      toast({
        title: "Gagal menghapus",
        description: "Pastikan backend server sudah di-update untuk mendukung fitur delete.",
        variant: "destructive"
      });
    } finally {
      setIsDeleting(false);
      closeDeleteModal();
    }
  };

  // Modal content helper
  const getModalContent = () => {
    switch (deleteModal.type) {
      case 'single':
        return {
          title: "Hapus Percakapan?",
          description: "Apakah Anda yakin ingin menghapus sesi percakapan ini? Tindakan ini tidak dapat dibatalkan.",
          confirmText: "Hapus Sesi"
        };
      case 'bulk':
        return {
          title: `Hapus ${selectedSessions.length} Percakapan?`,
          description: `Apakah Anda yakin ingin menghapus ${selectedSessions.length} sesi percakapan yang dipilih?`,
          confirmText: `Hapus ${selectedSessions.length} Item`
        };
      case 'all':
        return {
          title: "Hapus Semua Riwayat?",
          description: "Anda akan menghapus SELURUH riwayat percakapan Anda. Data yang hilang tidak dapat dikembalikan.",
          confirmText: "Hapus Semuanya"
        };
      default:
        return { title: "", description: "", confirmText: "" };
    }
  };
  
  const modalContent = getModalContent();

  return (
    <>
      <div
        className={`fixed left-0 top-0 h-full bg-white dark:bg-gray-800 border-r border-orange-200 dark:border-gray-700 shadow-lg transform transition-transform duration-300 flex flex-col w-80 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        } z-50`}
      >
        {/* Header */}
        <div className="flex-shrink-0 p-4 border-b border-orange-200 dark:border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <BrandLogo size="lg" showText={true} />
            <button
              onClick={onToggle}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors duration-200"
            >
              <ChevronLeft className="h-5 w-5 text-gray-600 dark:text-gray-300" />
            </button>
          </div>

          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <History className="h-4 w-4 text-orange-600" />
              <h2 className="text-base font-medium text-gray-800 dark:text-white">
                Chat History
              </h2>
            </div>

            {/* Toggle Selection Mode */}
            {sessions.length > 0 && (
              <button
                onClick={() => {
                  setIsSelectionMode(!isSelectionMode);
                  setSelectedSessions([]);
                }}
                className={`p-1.5 rounded transition-colors ${
                  isSelectionMode
                    ? 'bg-orange-100 text-orange-600'
                    : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400'
                }`}
                title={isSelectionMode ? "Batal Pilih" : "Pilih untuk dihapus"}
              >
                {isSelectionMode ? <X className="h-4 w-4" /> : <CheckSquare className="h-4 w-4" />}
              </button>
            )}
          </div>

          {/* Action Buttons */}
          <div className="space-y-2">
            {!isSelectionMode ? (
              <>
                <button
                  onClick={handleNewChatClick}
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
                    Actions
                    <MoreHorizontal className="h-4 w-4 ml-auto" />
                  </button>

                  {showExportMenu && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-700 border border-orange-200 dark:border-gray-600 rounded-lg shadow-lg z-50 overflow-hidden">
                      <button
                        onClick={() => {
                          exportCurrentChat();
                          setShowExportMenu(false);
                        }}
                        className="w-full text-left px-3 py-2 hover:bg-orange-50 dark:hover:bg-gray-600 text-sm text-gray-700 dark:text-gray-200 flex items-center gap-2"
                      >
                        <FileText className="h-4 w-4" />
                        Export Current
                      </button>
                      <button
                        onClick={() => {
                          exportAllChats();
                          setShowExportMenu(false);
                        }}
                        className="w-full text-left px-3 py-2 hover:bg-orange-50 dark:hover:bg-gray-600 text-sm text-gray-700 dark:text-gray-200 flex items-center gap-2 border-t border-gray-100 dark:border-gray-600"
                      >
                        <Download className="h-4 w-4" />
                        Export All
                      </button>
                      <button
                        onClick={triggerDeleteAll}
                        className="w-full text-left px-3 py-2 hover:bg-red-50 dark:hover:bg-red-900/30 text-sm text-red-600 dark:text-red-400 flex items-center gap-2 border-t border-gray-100 dark:border-gray-600"
                      >
                        <AlertTriangle className="h-4 w-4" />
                        Delete All History
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <button
                onClick={triggerBulkDelete}
                disabled={selectedSessions.length === 0}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-all duration-200 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Trash2 className="h-4 w-4" />
                Hapus ({selectedSessions.length})
              </button>
            )}
          </div>
        </div>

        {/* Session List */}
        <div className="flex-1 overflow-y-auto p-4 min-h-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-300">
              <MessageSquare className="h-12 w-12 mx-auto mb-3 text-gray-300 dark:text-gray-500" />
              <p>Belum ada riwayat chat</p>
            </div>
          ) : (
            <div className="space-y-2">
              {sessions.map((session) => {
                const isActive = currentSession?.id && String(currentSession.id) === String(session.id);
                
                return (
                  <div
                    key={session.id}
                    onClick={() => handleSessionClick(session.id)}
                    className={`group relative p-3 rounded-lg cursor-pointer transition-all duration-200 border ${
                      isActive && !isSelectionMode
                        ? "bg-orange-50 dark:bg-gray-700 border-orange-200 dark:border-gray-600"
                        : "hover:bg-gray-50 dark:hover:bg-gray-700 border-transparent"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* Checkbox */}
                      {isSelectionMode && (
                        <div
                          onClick={(e) => toggleSelection(session.id, e)}
                          className="mt-1 text-gray-500 hover:text-orange-600 cursor-pointer"
                        >
                          {selectedSessions.includes(session.id) ? (
                            <CheckSquare className="h-5 w-5 text-orange-600" />
                          ) : (
                            <Square className="h-5 w-5" />
                          )}
                        </div>
                      )}

                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-gray-800 dark:text-gray-100 truncate pr-6">
                          {session.title || "Untitled Chat"}
                        </h3>
                        <div className="flex items-center gap-2 mt-1 text-xs text-gray-500 dark:text-gray-300">
                          <Calendar className="h-3 w-3" />
                          <span>{formatDate(session.created_at)}</span>
                        </div>
                      </div>
                    </div>

                    {/* Active Indicator */}
                    {isActive && !isSelectionMode && (
                      <div className="absolute right-2 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-orange-600 rounded-full"></div>
                    )}

                    {/* Delete Button (Hover) */}
                    {!isSelectionMode && (
                      <button
                        onClick={(e) => triggerSingleDelete(session.id, e)}
                        className="absolute right-2 top-2 p-1.5 bg-white dark:bg-gray-800 rounded-md text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity shadow-sm border border-gray-100 dark:border-gray-600"
                        title="Hapus chat ini"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer Stats */}
        <div className="flex-shrink-0 p-4 border-t border-orange-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <div className="text-xs text-gray-600 dark:text-gray-300 space-y-1">
            <div className="flex justify-between">
              <span>Total Sessions:</span>
              <span className="font-medium">{sessions.length}</span>
            </div>
            <div className="flex justify-between">
              <span>Total Messages:</span>
              <span className="font-medium">{getTotalMessages()}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Backdrop for mobile */}
      {isOpen && (
        <div
          onClick={onToggle}
          className="fixed inset-0 bg-black bg-opacity-25 z-30 lg:hidden"
        />
      )}

      {/* Delete Confirmation Modal */}
      <DeleteConfirmationModal
        isOpen={deleteModal.isOpen}
        onClose={closeDeleteModal}
        onConfirm={handleConfirmDelete}
        title={modalContent.title}
        description={modalContent.description}
        confirmText={modalContent.confirmText}
        isLoading={isDeleting}
        type={deleteModal.type}
      />
    </>
  );
};

export default ChatSidebar;