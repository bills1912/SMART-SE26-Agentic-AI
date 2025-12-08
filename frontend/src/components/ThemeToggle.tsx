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
    <button
      onClick={toggleTheme}
      className="p-1 rounded border border-orange-200 dark:border-gray-700 bg-white/80 dark:bg-gray-800/80 hover:bg-orange-50 dark:hover:bg-gray-700 transition-all duration-200 group relative"
      aria-label={getNextThemeLabel()}
      title={getThemeLabel()}
    >
      {getThemeIcon()}
      
      {/* System sync indicator - smaller */}
      {themeMode === 'system' && (
        <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-green-500 border border-white dark:border-gray-800 rounded-full"></div>
      )}
      
      {/* Tooltip - Compact */}
      <div className="absolute bottom-full mb-1 left-1/2 transform -translate-x-1/2 bg-gray-900 dark:bg-gray-700 text-white text-[10px] py-1 px-2 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-[9999]">
        {getThemeLabel()}
      </div>
    </button>
  );
};

export default ThemeToggle;