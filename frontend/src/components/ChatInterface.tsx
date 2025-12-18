import React, { useState, useRef, useEffect, useCallback } from "react";
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
import { useParams, useNavigate } from "react-router-dom";

const ChatInterface: React.FC = () => {
  const {
    currentSession,
    addMessageToCurrentSession,
    updateMessageInCurrentSession,
    createNewChat,
    exportCurrentChat,
    switchToSession,
    isLoading: isContextLoading,
  } = useChat();

  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [scrapingStatus, setScrapingStatus] = useState<"idle" | "in_progress">("idle");
  const [isBackendAvailable, setIsBackendAvailable] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isLongLoading, setIsLongLoading] = useState(false);
  
  // Track jika sedang dalam proses switching untuk mencegah race condition
  const [isSwitching, setIsSwitching] = useState(false);
  const switchingRef = useRef(false);
  const lastSessionIdRef = useRef<string | undefined>(undefined);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mainContainerRef = useRef<HTMLDivElement>(null);

  // Determine if this is a new chat (no sessionId in URL)
  const isNewChat = !sessionId;

  // Get current session ID as string for comparison
  const currentSessionId = currentSession?.id ? String(currentSession.id) : "";

  // Calculate if we're waiting for session data
  const isSessionLoading = 
    isSwitching || 
    (!!sessionId && isContextLoading) ||
    (!!sessionId && currentSessionId !== sessionId && !isNewChat);

  // --- EFFECT: Handle URL changes and session switching ---
  useEffect(() => {
    const handleSessionChange = async () => {
      // Prevent concurrent switches
      if (switchingRef.current) {
        console.log("[ChatInterface] Switch already in progress, skipping");
        return;
      }

      // Skip if URL hasn't actually changed
      if (lastSessionIdRef.current === sessionId) {
        return;
      }

      lastSessionIdRef.current = sessionId;

      if (sessionId) {
        // URL has sessionId - switch to that session
        if (currentSessionId !== sessionId) {
          console.log(`[ChatInterface] Switching to session: ${sessionId}`);
          switchingRef.current = true;
          setIsSwitching(true);
          
          try {
            await switchToSession(sessionId);
          } catch (error) {
            console.error("[ChatInterface] Failed to switch session:", error);
            toast({
              title: "Error",
              description: "Gagal memuat sesi percakapan",
              variant: "destructive",
            });
          } finally {
            switchingRef.current = false;
            setIsSwitching(false);
          }
        }
      } else {
        // No sessionId in URL - create new chat
        console.log("[ChatInterface] Creating new chat (dashboard)");
        switchingRef.current = true;
        setIsSwitching(true);
        
        try {
          createNewChat();
          setInputMessage("");
          setIsLoading(false);
        } finally {
          // Small delay to ensure state is updated
          setTimeout(() => {
            switchingRef.current = false;
            setIsSwitching(false);
          }, 100);
        }
      }
    };

    handleSessionChange();
  }, [sessionId]); // Only depend on sessionId URL param

  // --- Handle New Chat button click ---
  const handleNewChat = useCallback(() => {
    if (switchingRef.current) return;
    
    console.log("[ChatInterface] New chat button clicked");
    lastSessionIdRef.current = undefined;
    createNewChat();
    setInputMessage("");
    setIsLoading(false);
    navigate("/dashboard", { replace: true });
  }, [createNewChat, navigate]);

  // --- Handle Session Switch from Sidebar ---
  const handleSwitchSession = useCallback(async (targetSessionId: string) => {
    if (switchingRef.current) {
      console.log("[ChatInterface] Switch blocked - already switching");
      return;
    }
    
    if (currentSessionId === targetSessionId) {
      console.log("[ChatInterface] Already on this session");
      setSidebarOpen(false);
      return;
    }

    console.log(`[ChatInterface] Manual switch to: ${targetSessionId}`);
    lastSessionIdRef.current = targetSessionId;
    navigate(`/c/${targetSessionId}`, { replace: true });
    setSidebarOpen(false);
  }, [currentSessionId, navigate]);

  const handleVoiceTranscript = (transcript: string) => {
    if (transcript.trim()) {
      setInputMessage((prev) => (prev + " " + transcript).trim());
      textareaRef.current?.focus();
    }
  };

  const messages = currentSession?.messages || [];
  const realMessages = messages.filter(
    (msg) => !msg.id?.startsWith("welcome_")
  );

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const scrollToTop = () => {
    if (mainContainerRef.current) {
      mainContainerRef.current.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  // Safety Timeout: If loading stuck > 5 seconds
  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    if (isSessionLoading) {
      setIsLongLoading(false);
      timeoutId = setTimeout(() => setIsLongLoading(true), 5000);
    } else {
      setIsLongLoading(false);
    }
    return () => clearTimeout(timeoutId);
  }, [isSessionLoading]);

  // Scroll management
  useEffect(() => {
    if (realMessages.length > 0) {
      if (realMessages.length <= 2) setTimeout(scrollToTop, 300);
      else scrollToBottom();
    }
  }, [realMessages.length]);

  // Check backend status on mount
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
    if (!inputMessage.trim() || isLoading || switchingRef.current) return;

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

      // If this is a new chat, navigate to the new session URL
      if (!sessionId && response.session_id) {
        lastSessionIdRef.current = response.session_id;
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
        description: `Analysis generated successfully. ${
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
          "I apologize, but I encountered an issue. Please try again in a moment.",
        timestamp: new Date(),
      };

      addMessageToCurrentSession(errorResponse);

      toast({
        title: "Connection Error",
        description: isBackendAvailable
          ? "Failed to analyze. Please try again."
          : "AI service is temporarily unavailable.",
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

  // Loading State UI
  if (isSessionLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 dark:bg-gray-900 flex-col px-4">
        <div className="text-center mb-6">
          <Loader2 className="h-10 w-10 animate-spin text-orange-600 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-300 font-medium">
            Mengambil riwayat percakapan...
          </p>
          {isLongLoading && (
            <p className="text-sm text-gray-400 mt-2 animate-pulse">
              Sedikit lebih lama dari biasanya...
            </p>
          )}
        </div>

        {isLongLoading && (
          <div className="flex flex-col gap-3 items-center animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center gap-2 text-amber-600 bg-amber-50 dark:bg-amber-900/20 px-4 py-2 rounded-lg border border-amber-200 dark:border-amber-800 text-sm mb-2">
              <AlertCircle className="h-4 w-4" />
              <span>Koneksi atau ID sesi mungkin bermasalah.</span>
            </div>

            <button
              onClick={handleNewChat}
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
      {/* Chat Sidebar */}
      <ChatSidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onSwitchSession={handleSwitchSession}
        onNewChat={handleNewChat}
      />

      {/* Backdrop for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Collapsed Sidebar - Desktop only */}
      {!sidebarOpen && (
        <div className="hidden lg:block">
          <CollapsedSidebar
            onNewChat={handleNewChat}
            onShowHistory={() => setSidebarOpen(true)}
            onExport={exportCurrentChat}
          />
        </div>
      )}

      <div
        ref={mainContainerRef}
        className={`flex-1 h-screen overflow-y-auto transition-all duration-300 ${
          sidebarOpen ? "lg:ml-80" : "lg:ml-16"
        }`}
      >
        {/* Header */}
        <div className="border-b border-gray-200 dark:border-gray-700 px-3 py-1 sticky top-0 bg-white dark:bg-gray-900 z-10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
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

            <div className="flex items-center gap-1">
              <ThemeToggle />
              <UserMenu />
            </div>
          </div>
        </div>

        {/* Main Content */}
        {isNewChat ? (
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

        {/* Input Area - Only show when not new chat */}
        {!isNewChat && (
          <div className="sticky bottom-0 pb-4 bg-gradient-to-t from-white via-white to-transparent dark:from-gray-900 dark:via-gray-900 dark:to-transparent pt-4">
            <div className="mx-auto px-4 max-w-4xl">
              <div className="border border-gray-300 dark:border-gray-600 rounded-2xl bg-white dark:bg-gray-800 overflow-hidden focus-within:ring-1 focus-within:ring-orange-500 dark:focus-within:ring-orange-400 transition-all duration-200">
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
                <div className="flex items-center justify-between px-4 py-2 bg-white dark:bg-gray-800">
                  <div className="flex items-center">
                    <VoiceRecorder
                      onTranscriptChange={handleVoiceTranscript}
                      disabled={isLoading}
                    />
                  </div>
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
              <div className="flex flex-col items-center justify-center mt-2 px-1 text-[10px] text-gray-500 dark:text-gray-400 gap-1.5">
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