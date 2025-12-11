import React, { useRef, useEffect } from 'react';
import { Sparkles, Send, Loader2, Database } from 'lucide-react';
// Pastikan path import VoiceRecorder sesuai
import VoiceRecorder from './VoiceRecorder'; 

interface NewChatWelcomeProps {
  inputMessage: string;
  setInputMessage: (msg: string) => void;
  handleSendMessage: () => void;
  isLoading: boolean;
  onVoiceTranscript: (text: string) => void;
}

const NewChatWelcome: React.FC<NewChatWelcomeProps> = ({ 
  inputMessage, 
  setInputMessage, 
  handleSendMessage, 
  isLoading,
  onVoiceTranscript
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Auto-focus saat halaman dimuat
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] px-4 w-full max-w-3xl mx-auto transition-all duration-500">
      
      {/* 1. GREETING SECTION */}
      <div className="text-center space-y-4 mb-8 w-full">
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-red-500 to-orange-600 rounded-2xl flex items-center justify-center shadow-lg transform hover:scale-105 transition-transform duration-300">
            <Sparkles className="h-8 w-8 text-white" />
          </div>
        </div>
        
        <h1 className="text-4xl font-serif font-medium text-gray-900 dark:text-white tracking-tight">
          Asisten Sensus Ekonomi Indonesia
        </h1>
        <p className="text-lg text-gray-500 dark:text-gray-400">
          Saya siap membantu analisis data dan metodologi sensus
        </p>
      </div>

      {/* 2. CENTERED INPUT BOX (Claude Style) */}
      <div className="w-full mb-8">
        <div className="relative bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-sm hover:shadow-md transition-shadow duration-300 overflow-hidden focus-within:ring-2 focus-within:ring-orange-500/50">
          <textarea
            ref={textareaRef}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Apa yang ingin Anda ketahui hari ini?"
            className="w-full px-5 py-4 bg-transparent text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 resize-none text-base custom-scrollbar focus:outline-none"
            style={{ minHeight: '80px', maxHeight: '200px' }}
            disabled={isLoading}
          />
          
          <div className="flex items-center justify-between px-3 py-2 bg-gray-50/50 dark:bg-gray-800/50">
             <div className="flex items-center gap-2">
                <VoiceRecorder onTranscriptChange={onVoiceTranscript} disabled={isLoading} />
             </div>
             <button
                onClick={handleSendMessage}
                disabled={isLoading || !inputMessage.trim()}
                className={`p-2 rounded-lg transition-all duration-200 ${
                  inputMessage.trim() 
                    ? 'bg-orange-600 text-white hover:bg-orange-700 shadow-sm' 
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                }`}
              >
                {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
          </div>
        </div>
        <div className="mt-2 text-center">
            <p className="text-xs text-gray-400 dark:text-gray-500 flex items-center justify-center gap-2">
               <span>AI can make mistakes. Please verify important information.</span>
            </p>
        </div>
      </div>

      {/* 3. SUGGESTIONS (Pills) */}
      <div className="flex flex-wrap justify-center gap-3 w-full">
        {[
          "Metodologi Sensus 2026",
          "Publikasi Hasil Sensus",
          "Sektor Ekonomi Indonesia",
          "Pelaksanaan Sensus"
        ].map((text, idx) => (
          <button 
            key={idx}
            onClick={() => setInputMessage(text)}
            className="px-4 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-full text-sm text-gray-600 dark:text-gray-300 hover:border-orange-500 dark:hover:border-orange-500 hover:text-orange-600 dark:hover:text-orange-400 transition-all duration-200 hover:shadow-sm"
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
};

export default NewChatWelcome;