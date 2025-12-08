import React from 'react';
import { Plus, History, Download, Settings } from 'lucide-react';
import BrandLogo from './BrandLogo';

interface CollapsedSidebarProps {
  onNewChat: () => void;
  onShowHistory: () => void;
  onExport: () => void;
}

const CollapsedSidebar: React.FC<CollapsedSidebarProps> = ({ 
  onNewChat, 
  onShowHistory,
  onExport 
}) => {
  return (
    <div className="fixed left-0 top-0 h-screen w-16 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col items-center py-4 z-30">
      {/* Brand Logo at Top - Clickable to Expand Sidebar */}
      <button
        onClick={onShowHistory}
        className="mb-6 w-12 h-12 flex items-center justify-center rounded-lg hover:bg-orange-50 dark:hover:bg-gray-700 transition-all duration-200 group relative"
        title="Expand Sidebar"
      >
        <BrandLogo size="md" showText={false} />
        
        {/* Expand Icon on Hover - appears next to logo */}
        <div className="absolute left-full ml-2 px-3 py-1.5 bg-gray-900 dark:bg-gray-700 text-white text-sm rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50 flex items-center gap-2">
          <span>Expand Sidebar</span>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </button>

      {/* Action Icons */}
      <div className="flex-1 flex flex-col gap-3">
        {/* New Chat */}
        <button
          onClick={onNewChat}
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-orange-50 dark:hover:bg-gray-700 transition-colors duration-200 group relative"
          title="New Chat"
        >
          <Plus className="h-5 w-5 text-gray-600 dark:text-gray-300" />
          
          {/* Tooltip */}
          <div className="absolute left-full ml-2 px-3 py-1.5 bg-gray-900 dark:bg-gray-700 text-white text-sm rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50">
            New Chat
          </div>
        </button>

        {/* Chat History */}
        <button
          onClick={onShowHistory}
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-orange-50 dark:hover:bg-gray-700 transition-colors duration-200 group relative"
          title="Chat History"
        >
          <History className="h-5 w-5 text-gray-600 dark:text-gray-300" />
          
          {/* Tooltip */}
          <div className="absolute left-full ml-2 px-3 py-1.5 bg-gray-900 dark:bg-gray-700 text-white text-sm rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50">
            Chat History
          </div>
        </button>

        {/* Export */}
        <button
          onClick={onExport}
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-orange-50 dark:hover:bg-gray-700 transition-colors duration-200 group relative"
          title="Export Chat"
        >
          <Download className="h-5 w-5 text-gray-600 dark:text-gray-300" />
          
          {/* Tooltip */}
          <div className="absolute left-full ml-2 px-3 py-1.5 bg-gray-900 dark:bg-gray-700 text-white text-sm rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50">
            Export Chat
          </div>
        </button>
      </div>

      {/* Settings at Bottom */}
      <button
        className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-orange-50 dark:hover:bg-gray-700 transition-colors duration-200 group relative"
        title="Settings"
      >
        <Settings className="h-5 w-5 text-gray-600 dark:text-gray-300" />
        
        {/* Tooltip */}
        <div className="absolute left-full ml-2 px-3 py-1.5 bg-gray-900 dark:bg-gray-700 text-white text-sm rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50">
          Settings
        </div>
      </button>
    </div>
  );
};

export default CollapsedSidebar;
