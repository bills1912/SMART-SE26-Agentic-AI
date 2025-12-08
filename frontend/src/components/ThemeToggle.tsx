import React from 'react';
import { Moon, Sun, Monitor } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

const ThemeToggle: React.FC = () => {
  const { themeMode, resolvedTheme, toggleTheme } = useTheme();

  const getThemeIcon = () => {
    switch (themeMode) {
      case 'light':
        return <Sun className="h-3.5 w-3.5 text-orange-600" />;
      case 'dark':
        return <Moon className="h-3.5 w-3.5 text-orange-400" />;
      case 'system':
        return <Monitor className="h-3.5 w-3.5 text-orange-500" />;
      default:
        return <Sun className="h-3.5 w-3.5 text-orange-600" />;
    }
  };

  const getThemeLabel = () => {
    switch (themeMode) {
      case 'light':
        return 'Light mode';
      case 'dark':
        return 'Dark mode';
      case 'system':
        return `System mode (${resolvedTheme})`;
      default:
        return 'Theme';
    }
  };

  const getNextThemeLabel = () => {
    switch (themeMode) {
      case 'light':
        return 'Switch to dark mode';
      case 'dark':
        return 'Switch to system sync';
      case 'system':
        return 'Switch to light mode';
      default:
        return 'Toggle theme';
    }
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={toggleTheme}
        className="p-2 rounded-lg border border-orange-200 dark:border-gray-700 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm hover:bg-orange-50 dark:hover:bg-gray-700 transition-all duration-200 shadow-md group relative"
        aria-label={getNextThemeLabel()}
        title={getThemeLabel()}
      >
        {getThemeIcon()}
        
        {/* System sync indicator */}
        {themeMode === 'system' && (
          <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 border-2 border-white dark:border-gray-800 rounded-full animate-pulse"></div>
        )}
        
        {/* Tooltip - Fixed with proper z-index and positioning */}
        <div className="absolute bottom-full mb-2 left-1/2 transform -translate-x-1/2 bg-gray-900 dark:bg-gray-700 text-white text-xs py-2 px-3 rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-[9999] shadow-lg">
          {getThemeLabel()}
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900 dark:border-t-gray-700"></div>
        </div>
      </button>
      
      {/* Theme mode text (optional, for larger screens) */}
      <div className="hidden md:block text-xs text-gray-600 dark:text-gray-400 min-w-0">
        <div className="capitalize font-medium">{themeMode}</div>
        {themeMode === 'system' && (
          <div className="text-green-600 dark:text-green-400 text-xs">Synced</div>
        )}
      </div>
    </div>
  );
};

export default ThemeToggle;