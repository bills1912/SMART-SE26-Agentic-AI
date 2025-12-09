import React from 'react';
import { Sparkles } from 'lucide-react';

interface NewChatWelcomeProps {
  onMessageSend?: () => void;
}

const NewChatWelcome: React.FC<NewChatWelcomeProps> = () => {
  return (
    <div className="flex-1 flex items-center justify-center px-4 py-12">
      <div className="max-w-3xl w-full text-center space-y-1">
        {/* Icon & Greeting - Compact spacing */}
        <div className="space-y-3">
          <div className="flex justify-center">
            <div className="w-16 h-16 bg-gradient-to-br from-red-500 to-orange-600 rounded-2xl flex items-center justify-center shadow-lg">
              <Sparkles className="h-8 w-8 text-white" />
            </div>
          </div>
          
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold text-gray-900 dark:text-white">
              Asisten Sensus Ekonomi Indonesia
            </h1>
            <p className="text-base text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
              Saya siap membantu Anda dengan pertanyaan seputar Sensus Ekonomi Indonesia, metodologi sensus, dan analisis data ekonomi
            </p>
          </div>
        </div>

        {/* Quick Suggestions - Horizontal Single Row, Smaller */}
        <div className="flex flex-wrap justify-center gap-2 max-w-4xl mx-auto">
          <button className="group px-4 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-orange-500 dark:hover:border-orange-500 rounded-lg transition-all duration-200 hover:shadow-md">
            <div className="text-sm font-medium text-gray-900 dark:text-white">
              Metodologi Sensus 2026
            </div>
          </button>
          
          <button className="group px-4 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-orange-500 dark:hover:border-orange-500 rounded-lg transition-all duration-200 hover:shadow-md">
            <div className="text-sm font-medium text-gray-900 dark:text-white">
              Publikasi Hasil Sensus
            </div>
          </button>
          
          <button className="group px-4 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-orange-500 dark:hover:border-orange-500 rounded-lg transition-all duration-200 hover:shadow-md">
            <div className="text-sm font-medium text-gray-900 dark:text-white">
              Sektor Ekonomi Indonesia
            </div>
          </button>
          
          <button className="group px-4 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-orange-500 dark:hover:border-orange-500 rounded-lg transition-all duration-200 hover:shadow-md">
            <div className="text-sm font-medium text-gray-900 dark:text-white">
              Pelaksanaan Sensus
            </div>
          </button>
        </div>
      </div>
    </div>
  );
};

export default NewChatWelcome;
