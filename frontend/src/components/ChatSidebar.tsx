// src/components/ChatSidebar.tsx

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
  AlertTriangle // Tambah import AlertTriangle
} from "lucide-react";
import { useChat } from "../contexts/ChatContext";
import { format } from "date-fns";
import BrandLogo from "./BrandLogo";
import { toast } from "../hooks/use-toast";
// IMPORT MODAL BARU
import DeleteConfirmationModal from "./DeleteConfirmationModal";

interface ChatSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

// Tipe data untuk state modal
type DeleteModalState = {
    isOpen: boolean;
    type: 'single' | 'bulk' | 'all' | null;
    targetId?: string; // Hanya terisi jika type 'single'
};

const ChatSidebar: React.FC<ChatSidebarProps> = ({ isOpen, onToggle }) => {
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

  const [showExportMenu, setShowExportMenu] = useState(false);
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedSessions, setSelectedSessions] = useState<string[]>([]);

  // --- MODAL STATE & LOADING STATE UNTUK DELETE ---
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

  // --- Logic Selection ---
  const toggleSelection = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (selectedSessions.includes(sessionId)) {
      setSelectedSessions(prev => prev.filter(id => id !== sessionId));
    } else {
      setSelectedSessions(prev => [...prev, sessionId]);
    }
  };

  // --- MODAL TRIGGERS (Hanya membuka modal, tidak langsung hapus) ---

  const triggerBulkDelete = () => {
    if (selectedSessions.length === 0) return;
    setDeleteModal({ isOpen: true, type: 'bulk' });
  };

  const triggerSingleDelete = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteModal({ isOpen: true, type: 'single', targetId: sessionId });
    // Tutup menu export jika terbuka
    setShowExportMenu(false); 
  };
  
  const triggerDeleteAll = () => {
      setDeleteModal({ isOpen: true, type: 'all' });
      setShowExportMenu(false);
  }

  const closeDeleteModal = () => {
      if (isDeleting) return; // Jangan tutup jika sedang proses
      setDeleteModal({ isOpen: false, type: null, targetId: undefined });
  };


  // --- CONFIRMATION LOGIC (Eksekusi hapus saat tombol di modal diklik) ---
  const handleConfirmDelete = async () => {
      setIsDeleting(true);
      try {
          if (deleteModal.type === 'single' && deleteModal.targetId) {
              await deleteSession(deleteModal.targetId);
              toast({ title: "Chat deleted successfully" });

          } else if (deleteModal.type === 'bulk') {
              await deleteMultipleSessions(selectedSessions);
              toast({ title: `${selectedSessions.length} chats deleted successfully` });
              // Reset selection mode setelah bulk delete
              setIsSelectionMode(false);
              setSelectedSessions([]);

          } else if (deleteModal.type === 'all') {
              await deleteAllSessions();
              toast({ title: "All chat history deleted successfully" });
          }
      } catch (error) {
          console.error("Delete failed:", error);
          toast({ 
              title: "Failed to delete", 
              description: "An error occurred while trying to delete the chat(s).", 
              variant: "destructive" 
          });
      } finally {
          setIsDeleting(false);
          closeDeleteModal();
      }
  }

  // Helper untuk konten modal dinamis
  const getModalContent = () => {
      switch (deleteModal.type) {
          case 'single':
              return {
                  title: "Delete Chat?",
                  description: "Are you sure you want to delete this chat session? This action cannot be undone.",
                  confirmText: "Delete Chat"
              };
          case 'bulk':
              return {
                  title: `Delete ${selectedSessions.length} Chats?`,
                  description: <>Are you sure you want to delete these <b>{selectedSessions.length}</b> selected chat sessions? This action cannot be undone.</>,
                  confirmText: `Delete ${selectedSessions.length} Chats`
              };
          case 'all':
              return {
                  title: "Delete All History?",
                  description: "Are you sure you want to delete ALL chat history? This is a destructive action and cannot be undone.",
                  confirmText: "Delete Everything"
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
             
             {/* Toggle Selection Mode Button */}
             {sessions.length > 0 && (
                 <button 
                    onClick={() => {
                        setIsSelectionMode(!isSelectionMode);
                        setSelectedSessions([]);
                    }}
                    className={`p-1.5 rounded transition-colors ${isSelectionMode ? 'bg-orange-100 text-orange-600' : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400'}`}
                    title={isSelectionMode ? "Cancel Selection" : "Select Chats to Delete"}
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
                        Actions
                        <MoreHorizontal className="h-4 w-4 ml-auto" />
                      </button>

                      {showExportMenu && (
                        <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-700 border border-orange-200 dark:border-gray-600 rounded-lg shadow-lg z-50 overflow-hidden">
                          <button
                            onClick={() => { exportCurrentChat(); setShowExportMenu(false); }}
                            className="w-full text-left px-3 py-2 hover:bg-orange-50 dark:hover:bg-gray-600 text-sm text-gray-700 dark:text-gray-200 flex items-center gap-2"
                          >
                            <FileText className="h-4 w-4" />
                            Export Current
                          </button>
                          <button
                            onClick={() => { exportAllChats(); setShowExportMenu(false); }}
                            className="w-full text-left px-3 py-2 hover:bg-orange-50 dark:hover:bg-gray-600 text-sm text-gray-700 dark:text-gray-200 flex items-center gap-2 border-t border-gray-100 dark:border-gray-600"
                          >
                            <Download className="h-4 w-4" />
                            Export All
                          </button>
                           {/* Tombol Delete All dengan Ikon Alert */}
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
                // Mode Seleksi Aktif - Tombol Bulk Delete
                <button
                  onClick={triggerBulkDelete}
                  disabled={selectedSessions.length === 0}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-all duration-200 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Trash2 className="h-4 w-4" />
                  Delete Selected ({selectedSessions.length})
                </button>
            )}
          </div>
        </div>

        {/* List Session */}
        <div className="flex-1 overflow-y-auto p-4 min-h-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-300">
              <MessageSquare className="h-12 w-12 mx-auto mb-3 text-gray-300 dark:text-gray-500" />
              <p>No chat history yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => !isSelectionMode && switchToSession(session.id)}
                  className={`group relative p-3 rounded-lg cursor-pointer transition-all duration-200 border ${
                    currentSession?.id === session.id && !isSelectionMode
                      ? "bg-orange-50 dark:bg-gray-700 border-orange-200 dark:border-gray-600"
                      : "hover:bg-gray-50 dark:hover:bg-gray-700 border-transparent"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {/* Checkbox untuk Selection Mode */}
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

                  {/* Indikator Active Session */}
                  {currentSession?.id === session.id && !isSelectionMode && (
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-orange-600 rounded-full"></div>
                  )}

                  {/* Tombol Delete Single (Hover Only) - Menggunakan triggerSingleDelete */}
                  {!isSelectionMode && (
                      <button
                        onClick={(e) => triggerSingleDelete(session.id, e)}
                        className="absolute right-2 top-2 p-1.5 bg-white dark:bg-gray-800 rounded-md text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity shadow-sm border border-gray-100 dark:border-gray-600"
                        title="Delete chat"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                  )}
                </div>
              ))}
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

      {/* Overlay untuk mobile */}
      {isOpen && (
        <div
          onClick={onToggle}
          className="fixed inset-0 bg-black bg-opacity-25 z-30 lg:hidden"
        />
      )}

      {/* --- RENDER MODAL CONFIRMATION DI SINI --- */}
      <DeleteConfirmationModal
          isOpen={deleteModal.isOpen}
          onClose={closeDeleteModal}
          onConfirm={handleConfirmDelete}
          title={modalContent.title}
          description={modalContent.description}
          confirmText={modalContent.confirmText}
          isLoading={isDeleting}
      />
    </>
  );
};

export default ChatSidebar;