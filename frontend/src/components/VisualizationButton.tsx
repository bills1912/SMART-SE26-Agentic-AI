import React from 'react';
import { TrendingUp, ChevronRight, BarChart3 } from 'lucide-react';

interface VisualizationButtonProps {
  count: number;
  onClick: () => void;
  title?: string;
}

const VisualizationButton: React.FC<VisualizationButtonProps> = ({ 
  count, 
  onClick,
  title = "Data Visualizations"
}) => {
  return (
    <button
      onClick={onClick}
      className="group relative w-full mt-3 flex items-center justify-between px-4 py-3 bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 hover:border-orange-500 dark:hover:border-orange-500 rounded-xl transition-all duration-200 hover:shadow-md"
    >
      {/* Left side: Icon + Text */}
      <div className="flex items-center gap-3">
        {/* Icon */}
        <div className="w-10 h-10 bg-gradient-to-br from-red-500 to-orange-600 rounded-lg flex items-center justify-center flex-shrink-0">
          <BarChart3 className="h-5 w-5 text-white" />
        </div>
        
        {/* Text */}
        <div className="text-left">
          <div className="text-sm font-semibold text-gray-900 dark:text-white">
            {title}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {count} {count === 1 ? 'chart' : 'charts'} available
          </div>
        </div>
      </div>

      {/* Right side: Arrow */}
      <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-orange-600 transition-colors" />

      {/* Hover effect overlay */}
      <div className="absolute inset-0 bg-gradient-to-r from-red-500/5 to-orange-500/5 opacity-0 group-hover:opacity-100 rounded-xl transition-opacity duration-200" />
    </button>
  );
};

export default VisualizationButton;
