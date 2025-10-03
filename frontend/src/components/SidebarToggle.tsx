import React, { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import BrandLogo from './BrandLogo';

interface SidebarToggleProps {
  isOpen: boolean;
  onToggle: () => void;
}

const SidebarToggle: React.FC<SidebarToggleProps> = ({ isOpen, onToggle }) => {
  const [isHovered, setIsHovered] = useState(false);

  if (isOpen) return null;

  return (
    <button
      onClick={onToggle}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="fixed left-4 top-4 z-30 p-3 bg-white dark:bg-gray-800 border border-orange-200 dark:border-gray-700 rounded-xl shadow-lg hover:shadow-xl hover:bg-orange-50 dark:hover:bg-gray-700 transition-all duration-300 group"
      aria-label="Open sidebar"
    >
      <div className="flex items-center justify-center w-6 h-6 relative overflow-hidden">
        {/* Logo - slides out on hover */}
        <div className={`absolute inset-0 flex items-center justify-center transition-transform duration-300 ${
          isHovered ? '-translate-x-8 opacity-0' : 'translate-x-0 opacity-100'
        }`}>
          <BrandLogo size="sm" showText={false} />
        </div>
        
        {/* Arrow - slides in on hover */}
        <div className={`absolute inset-0 flex items-center justify-center transition-transform duration-300 ${
          isHovered ? 'translate-x-0 opacity-100' : 'translate-x-8 opacity-0'
        }`}>
          <ChevronRight className="h-5 w-5 text-orange-600 dark:text-orange-400" />
        </div>
      </div>
      
      {/* Tooltip */}
      <div className="absolute left-full ml-3 top-1/2 transform -translate-y-1/2 bg-gray-900 dark:bg-gray-700 text-white text-xs py-1 px-2 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50">
        Open Chat History
        <div className="absolute right-full top-1/2 transform -translate-y-1/2 w-0 h-0 border-t-2 border-b-2 border-r-2 border-transparent border-r-gray-900 dark:border-r-gray-700"></div>
      </div>
    </button>
  );
};

export default SidebarToggle;