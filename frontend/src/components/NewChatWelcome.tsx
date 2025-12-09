import React from 'react';
import { Sparkles } from 'lucide-react';

interface NewChatWelcomeProps {
  onMessageSend?: () => void;
}

const NewChatWelcome: React.FC<NewChatWelcomeProps> = () => {
  return (
    <div className="flex-1 flex items-center justify-center px-4 animate-in fade-in duration-500">
      <div className="max-w-2xl w-full text-center space-y-8">
        {/* Icon & Greeting */}
        <div className="space-y-4">
          <div className="flex justify-center">
            <div className="w-16 h-16 bg-gradient-to-br from-red-500 to-orange-600 rounded-2xl flex items-center justify-center shadow-lg">
              <Sparkles className="h-8 w-8 text-white" />
            </div>
          </div>
          
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold text-gray-900 dark:text-white">
              Asisten Sensus Ekonomi Indonesia
            </h1>
            <p className="text-lg text-gray-600 dark:text-gray-400">
              Saya siap membantu Anda dengan pertanyaan seputar Sensus Ekonomi Indonesia, metodologi sensus, dan analisis data ekonomi
            </p>
          </div>
        </div>

        {/* Quick Suggestions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-xl mx-auto">
          <button className="group p-4 bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 hover:border-orange-500 dark:hover:border-orange-500 rounded-xl text-left transition-all duration-200 hover:shadow-md">
            <div className="text-sm font-medium text-gray-900 dark:text-white mb-1">
              Metodologi Sensus 2026
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              Jelaskan metodologi yang akan digunakan
            </div>
          </button>
          
          <button className="group p-4 bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 hover:border-orange-500 dark:hover:border-orange-500 rounded-xl text-left transition-all duration-200 hover:shadow-md">
            <div className="text-sm font-medium text-gray-900 dark:text-white mb-1">
              Publikasi Hasil Sensus
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              Bagaimana cara mengakses data sensus?
            </div>
          </button>
          
          <button className="group p-4 bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 hover:border-orange-500 dark:hover:border-orange-500 rounded-xl text-left transition-all duration-200 hover:shadow-md">
            <div className="text-sm font-medium text-gray-900 dark:text-white mb-1">
              Sektor Ekonomi Indonesia
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              Analisis sektoral ekonomi Indonesia
            </div>
          </button>
          
          <button className="group p-4 bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 hover:border-orange-500 dark:hover:border-orange-500 rounded-xl text-left transition-all duration-200 hover:shadow-md">
            <div className="text-sm font-medium text-gray-900 dark:text-white mb-1">
              Pelaksanaan Sensus
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              Tahapan pelaksanaan kegiatan sensus
            </div>
          </button>
        </div>
      </div>
    </div>
  );
};

export default NewChatWelcome;
