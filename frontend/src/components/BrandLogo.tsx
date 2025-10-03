import React from 'react';
import { Bot } from 'lucide-react';

interface BrandLogoProps {
  size?: 'sm' | 'md' | 'lg';
  showText?: boolean;
  className?: string;
}

const BrandLogo: React.FC<BrandLogoProps> = ({ size = 'md', showText = true, className = '' }) => {
  const sizeClasses = {
    sm: {
      container: 'w-6 h-6',
      icon: 'h-3 w-3',
      text: 'text-sm font-semibold',
      gap: 'gap-2'
    },
    md: {
      container: 'w-8 h-8',
      icon: 'h-4 w-4',
      text: 'text-base font-bold',
      gap: 'gap-3'
    },
    lg: {
      container: 'w-10 h-10',
      icon: 'h-5 w-5',
      text: 'text-lg font-bold',
      gap: 'gap-3'
    }
  };

  const config = sizeClasses[size];

  return (
    <div className={`flex items-center ${config.gap} ${className}`}>
      {/* Brand Icon */}
      <div className={`${config.container} bg-gradient-to-br from-red-500 to-orange-600 rounded-lg flex items-center justify-center flex-shrink-0`}>
        <Bot className={`${config.icon} text-white`} />
      </div>
      
      {/* Brand Text */}
      {showText && (
        <div className="flex flex-col min-w-0">
          <div className={`${config.text} bg-gradient-to-r from-red-600 to-orange-600 bg-clip-text text-transparent leading-tight`}>
            PolicyAI
          </div>
          {size !== 'sm' && (
            <div className="text-xs text-gray-500 dark:text-gray-400 leading-tight">
              Insight Generator
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default BrandLogo;