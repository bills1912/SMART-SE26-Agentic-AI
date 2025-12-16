import React, { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2, Database, Menu, AlertCircle, ArrowLeft } from "lucide-react";
import { ChatMessage } from "../types/chat";
import MessageBubble from "./MessageBubble";
import { toast } from "../hooks/use-toast";
import apiService from "../services/api";
import ThemeToggle from "./ThemeToggle";
import ChatSidebar from "./ChatSidebar";
import CollapsedSidebar from "./CollapsedSidebar";
import VoiceRecorder from "./VoiceRecorder";
import UserMenu from "./UserMenu";
import NewChatWelcome from "./NewChatWelcome";
import { useChat } from "../contexts/ChatContext";
import { useParams, useNavigate, useLocation } from "react-router-dom";

const ChatInterface: React.FC = () => {
  const {
    currentSession,
    addMessageToCurrentSession,
    updateMessageInCurrentSession,
    createNewChat,
    exportCurrentChat,
    switchToSession, 
    sessions, 
    isLoading: isContextLoading,
  } = useChat();

  // 2. Init Hooks Router
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [scrapingStatus, setScrapingStatus] = useState<"idle" | "in_progress">("idle");
  const [isBackendAvailable, setIsBackendAvailable] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  // IMPROVISASI: State untuk mendeteksi loading yang terlalu lama (stuck)
  const [isLongLoading, setIsLongLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mainContainerRef = useRef<HTMLDivElement>(null);

  // Handle voice transcript
  const handleVoiceTranscript = (transcript: string) => {
    if (transcript.trim()) {
      setInputMessage((prev) => (prev + " " + transcript).trim());
      textareaRef.current?.focus();
    }
  };

  // Get messages from current session
  const messages = currentSession?.messages || [];

  // Filter out welcome messages to show welcome screen for new chat
  const realMessages = messages.filter(
    (msg) => !msg.id?.startsWith("welcome_")
  );

  // --- LOGIC PERBAIKAN LOADING & STATUS (BUG FIX NUMBER VS STRING) ---
  
  // Check if this is a new empty chat
  const isNewChat = !sessionId;

  // FIX: Kita konversi currentSession.id ke String sebelum membandingkan.
  // Ini mengatasi masalah di mana API mengembalikan ID angka (number) tapi URL adalah string.
  const isIdMismatch = sessionId && currentSession?.id && String(currentSession.id) !== sessionId;

  // Kita anggap "Loading Session" jika:
  // 1. Ada ID di URL tapi context belum punya session sama sekali.
  // 2. Ada ID di URL tapi ID-nya tidak cocok dengan yang ada di context (Mismatch).
  // 3. Context sendiri sedang status loading.
  const isSessionLoading =
    (!!sessionId && !currentSession) ||
    (!!sessionId && isIdMismatch) ||
    (isContextLoading && !!sessionId);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const scrollToTop = () => {
    if (mainContainerRef.current) {
      mainContainerRef.current.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  // IMPROVISASI: Safety Timeout Effect
  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    if (isSessionLoading) {
      setIsLongLoading(false); // Reset saat mulai loading
      timeoutId = setTimeout(() => {
        setIsLongLoading(true); // Trigger UI bantuan jika stuck > 5 detik
      }, 5000); 
    } else {
      setIsLongLoading(false);
    }

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [isSessionLoading]);

  // Scroll management for messages
  useEffect(() => {
    if (realMessages.length > 0) {
      if (realMessages.length <= 2) {
        setTimeout(() => {
          scrollToTop();
        }, 300);
      } else {
        scrollToBottom();
      }
    }
  }, [realMessages.length]);

  // --- CORE FIX: PERBAIKAN LOGIKA SWITCH SESSION & NEW CHAT ---

  // FIX 1: Handle Perubahan Sesi (History Click)
  // Menambahkan dependency currentSession?.id dan String conversion check
  useEffect(() => {
    if (sessionId) {
      // Cek menggunakan string conversion agar aman
      const currentIdString = currentSession?.id ? String(currentSession.id) : "";
      
      if (currentIdString !== sessionId) {
        try {
          // Panggil switch session
          switchToSession(sessionId);
        } catch (error) {
          console.error("Error triggering switch session:", error);
        }
      }
    }
  }, [sessionId, currentSession?.id]); // Dependency diperbarui agar responsif

  // FIX 2: Handle New Chat (Dashboard Navigation)
  useEffect(() => {
    // Jika kita di dashboard (tidak ada sessionId) TAPI masih ada sesi nyangkut di memori
    if (!sessionId && location.pathname.includes("/dashboard")) {
      if (currentSession?.id) {
        createNewChat();
        setInputMessage(""); // Pastikan input bersih
      }
    }
  }, [sessionId, location.pathname]); 

  // --- END CORE FIX ---

  useEffect(() => {
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
      console.error("Backend not available:", error);
    }
  };

  // Handle edit message - Claude style: edit and resubmit
  const handleEditMessage = async (messageId: string, newContent: string) => {
    if (!currentSession || !newContent.trim()) return;

    const messageIndex = currentSession.messages.findIndex(
      (msg) => msg.id === messageId
    );
    if (messageIndex === -1) return;

    if (updateMessageInCurrentSession) {
      updateMessageInCurrentSession(messageId, newContent);
    }

    const editedMessage = currentSession.messages[messageIndex];
    if (editedMessage.sender === "user") {
      setIsLoading(true);

      try {
        const response = await apiService.sendMessage(
          newContent,
          currentSession.id
        );

        const aiResponse: ChatMessage = {
          id: response.session_id + "_" + Date.now(),
          session_id: response.session_id,
          sender: "ai",
          content: response.message,
          timestamp: new Date(),
          visualizations: response.visualizations || [],
          insights: response.insights || [],
          policies: response.policies || [],
        };

        addMessageToCurrentSession(aiResponse);

        toast({
          title: "Message Updated",
          description: "Your message has been edited and a new response generated.",
        });
      } catch (error: any) {
        console.error("Error regenerating response:", error);
        toast({
          title: "Error",
          description: "Failed to regenerate response. Please try again.",
          variant: "destructive",
        });
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleRegenerateResponse = async (messageId: string) => {
    if (!currentSession || isLoading) return;

    const aiMessageIndex = currentSession.messages.findIndex(
      (msg) => msg.id === messageId
    );
    if (aiMessageIndex === -1) return;

    let userMessage: ChatMessage | null = null;
    for (let i = aiMessageIndex - 1; i >= 0; i--) {
      if (currentSession.messages[i].sender === "user") {
        userMessage = currentSession.messages[i];
        break;
      }
    }

    if (!userMessage) return;

    setIsLoading(true);

    try {
      const response = await apiService.sendMessage(
        userMessage.content,
        currentSession.id
      );

      if (updateMessageInCurrentSession) {
        updateMessageInCurrentSession(messageId, response.message);
      }

      toast({
        title: "Response Regenerated",
        description: "A new response has been generated.",
      });
    } catch (error: any) {
      console.error("Error regenerating response:", error);
      toast({
        title: "Error",
        description: "Failed to regenerate response. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async () => {
    // Diperbolehkan kirim pesan meski currentSession null (untuk trigger new chat otomatis)
    if (!inputMessage.trim() || isLoading) return;

    const activeSessionId = currentSession?.id || "";

    const userMessage: ChatMessage = {
      id: Math.random().toString(36).substr(2, 9),
      session_id: activeSessionId,
      sender: "user",
      content: inputMessage.trim(),
      timestamp: new Date(),
    };

    addMessageToCurrentSession(userMessage);

    const originalMessage = inputMessage.trim();
    setInputMessage("");
    setIsLoading(true);

    try {
      if (!isBackendAvailable) {
        throw new Error("Backend service is currently unavailable");
      }

      const response = await apiService.sendMessage(
        originalMessage,
        activeSessionId
      );

      // Jika kita berada di mode New Chat (tidak ada ID di URL),
      // maka setelah kirim pesan pertama, kita harus update URL ke session ID baru
      if (!sessionId && response.session_id) {
        navigate(`/c/${response.session_id}`, { replace: true });
      }

      const aiResponse: ChatMessage = {
        id: response.session_id + "_" + Date.now(),
        session_id: response.session_id,
        sender: "ai",
        content: response.message,
        timestamp: new Date(),
        visualizations: response.visualizations || [],
        insights: response.insights || [],
        policies: response.policies || [],
      };

      addMessageToCurrentSession(aiResponse);

      toast({
        title: "Analysis Complete",
        description: `AI policy analysis generated successfully. ${
          response.supporting_data_count > 0
            ? `Used ${response.supporting_data_count} data sources.`
            : ""
        }`,
      });

      const health = await apiService.getHealth();
      setScrapingStatus(health.scraping_status);
    } catch (error: any) {
      console.error("Error sending message:", error);

      const errorResponse: ChatMessage = {
        id: "error_" + Date.now(),
        session_id: activeSessionId,
        sender: "ai",
        content:
          "I apologize, but I encountered an issue while analyzing your policy question. This could be due to high demand or temporary service issues. Please try again in a moment.",
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
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // IMPROVISASI: Tampilan Loading dengan tombol Exit jika stuck
  if (isSessionLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 dark:bg-gray-900 flex-col px-4">
        <div className="text-center mb-6">
          <Loader2 className="h-10 w-10 animate-spin text-orange-600 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-300 font-medium">
            Mengambil riwayat percakapan...
          </p>
          {/* Tampilkan pesan tambahan jika loading > 5 detik */}
          {isLongLoading && (
            <p className="text-sm text-gray-400 mt-2 animate-pulse">
              Sedikit lebih lama dari biasanya...
            </p>
          )}
        </div>

        {/* IMPROVISASI: Tombol Emergency Exit jika loading stuck */}
        {isLongLoading && (
          <div className="flex flex-col gap-3 items-center animate-in fade-in slide-in-from-bottom-4 duration-500">
             <div className="flex items-center gap-2 text-amber-600 bg-amber-50 dark:bg-amber-900/20 px-4 py-2 rounded-lg border border-amber-200 dark:border-amber-800 text-sm mb-2">
                <AlertCircle className="h-4 w-4" />
                <span>Koneksi atau ID sesi mungkin bermasalah.</span>
             </div>
             
             <button 
                onClick={() => {
                   createNewChat();
                   navigate('/dashboard');
                }}
                className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg text-sm text-gray-700 dark:text-gray-200 transition-colors shadow-sm"
             >
                <ArrowLeft className="h-4 w-4" />
                Kembali ke Dashboard & Buat Chat Baru
             </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-white to-red-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 transition-colors duration-300">
      {/* Chat Sidebar - Overlay on mobile, fixed on desktop */}
      <ChatSidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Backdrop blur for mobile when sidebar open */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Collapsed Sidebar - Icons only when sidebar closed - DESKTOP ONLY */}
      {!sidebarOpen && (
        <div className="hidden lg:block">
          <CollapsedSidebar
            onNewChat={() => {
              createNewChat();
              navigate("/dashboard");
            }}
            onShowHistory={() => setSidebarOpen(true)}
            onExport={exportCurrentChat}
          />
        </div>
      )}

      {/* Main Content - Claude-style FULL SCREEN SCROLL */}
      <div
        ref={mainContainerRef}
        className={`flex-1 h-screen overflow-y-auto transition-all duration-300 ${
          sidebarOpen ? "lg:ml-80" : "lg:ml-16"
        }`}
      >
        {/* Compact Header */}
        <div className="border-b border-gray-200 dark:border-gray-700 px-3 py-1 sticky top-0 bg-white dark:bg-gray-900 z-10">
          <div className="flex items-center justify-between">
            {/* Left: Mobile menu button + Title */}
            <div className="flex items-center gap-1.5">
              {/* Mobile Menu Toggle Button */}
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="lg:hidden p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                aria-label="Toggle sidebar"
              >
                <Menu className="h-4 w-4 text-gray-600 dark:text-gray-300" />
              </button>

              <div className="w-5 h-5 bg-gradient-to-br from-red-500 to-orange-600 rounded flex items-center justify-center">
                <Bot className="h-2.5 w-2.5 text-white" />
              </div>
              <h1 className="text-sm font-medium text-gray-800 dark:text-white">
                AI Policy & Insight Generator
              </h1>
            </div>

            {/* Right: Controls */}
            <div className="flex items-center gap-1">
              <ThemeToggle />
              <UserMenu />
            </div>
          </div>
        </div>

        {/* Chat Messages Area OR Welcome Screen */}
        {isNewChat ? (
          // KONDISI 1: NEW CHAT (TAMPILAN TENGAH)
          <div className="flex flex-col justify-center min-h-[calc(100vh-60px)]">
            <NewChatWelcome
              inputMessage={inputMessage}
              setInputMessage={setInputMessage}
              handleSendMessage={handleSendMessage}
              isLoading={isLoading}
              onVoiceTranscript={handleVoiceTranscript}
            />
          </div>
        ) : (
          /* Normal Chat Messages */
          <div className="min-h-full transition-all duration-700 ease-in opacity-100">
            <div className="max-w-3xl mx-auto px-4 pt-3">
              <div className="space-y-6">
                {realMessages.map((message) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    onEdit={handleEditMessage}
                    onRegenerate={handleRegenerateResponse}
                  />
                ))}
                {isLoading && (
                  <div className="flex items-center gap-3 p-4">
                    <div className="w-8 h-8 bg-gradient-to-br from-red-500 to-orange-600 rounded-full flex items-center justify-center">
                      <Bot className="h-4 w-4 text-white" />
                    </div>
                    <div className="flex items-center gap-2 text-gray-600 dark:text-gray-200">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>
                        {scrapingStatus === "in_progress"
                          ? "Mengumpulkan data sensus terbaru..."
                          : "Menganalisis pertanyaan Anda..."}
                      </span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>
          </div>
        )}

        {/* Input Container */}
        {!isNewChat && (
          <div
            className={`sticky bottom-0 pb-4 transition-all duration-500 ${
              isNewChat
                ? "bg-transparent pt-3"
                : "bg-gradient-to-t from-white via-white to-transparent dark:from-gray-900 dark:via-gray-900 dark:to-transparent pt-4"
            }`}
          >
            <div
              className={`mx-auto px-4 transition-all duration-500 ${
                isNewChat ? "max-w-2xl" : "max-w-4xl"
              }`}
            >
              {/* Single Input Container */}
              <div className="border border-gray-300 dark:border-gray-600 rounded-2xl bg-white dark:bg-gray-800 overflow-hidden focus-within:ring-1 focus-within:ring-orange-500 dark:focus-within:ring-orange-400 transition-all duration-200">
                {/* Textarea Area */}
                <div className="relative">
                  <textarea
                    ref={textareaRef}
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Reply..."
                    className="w-full px-4 py-3 bg-transparent text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 resize-none text-sm custom-scrollbar focus:outline-none border-0 transition-none"
                    style={{
                      minHeight: "44px",
                      maxHeight: "120px",
                      boxShadow: "none",
                      outline: "none",
                    }}
                    disabled={isLoading}
                    rows={1}
                  />
                </div>

                {/* Controls Row */}
                <div className="flex items-center justify-between px-4 py-2 bg-white dark:bg-gray-800">
                  {/* Left: Voice Recording Button */}
                  <div className="flex items-center">
                    <VoiceRecorder
                      onTranscriptChange={handleVoiceTranscript}
                      disabled={isLoading}
                    />
                  </div>

                  {/* Right: Send Button */}
                  <div className="flex items-center">
                    <button
                      onClick={handleSendMessage}
                      disabled={isLoading || !inputMessage.trim()}
                      className="p-2 bg-gradient-to-r from-red-500 to-orange-600 hover:from-red-600 hover:to-orange-700 text-white rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                      title={isLoading ? "Analyzing..." : "Send message"}
                    >
                      {isLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* Status Text */}
              <div className="flex flex-col items-center justify-center mt-2 px-1 text-[10px] text-gray-500 dark:text-gray-400 gap-1.5">
                {/* Status Indicators - Centered */}
                <div className="flex items-center gap-2 sm:gap-3">
                  <div className="flex items-center gap-1">
                    <Database className="h-2 w-2 flex-shrink-0" />
                    <span
                      className={
                        scrapingStatus === "in_progress"
                          ? "text-orange-600 dark:text-orange-400"
                          : ""
                      }
                    >
                      {scrapingStatus === "in_progress"
                        ? "Gathering data..."
                        : "Data ready"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div
                      className={`w-1 h-1 rounded-full flex-shrink-0 ${
                        isBackendAvailable ? "bg-green-500" : "bg-red-500"
                      }`}
                    />
                    <span
                      className={
                        isBackendAvailable
                          ? "text-green-600 dark:text-green-400"
                          : "text-red-600 dark:text-red-400"
                      }
                    >
                      {isBackendAvailable ? "Connected" : "Offline"}
                    </span>
                  </div>
                </div>

                {/* AI Disclaimer - Centered */}
                <p className="text-gray-400 dark:text-gray-500 text-[9px] sm:text-[10px] text-center">
                  AI can make mistakes. Verify info.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatInterface;