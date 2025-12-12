import React, { useState, useRef, useEffect } from 'react';
import { Bot, User, TrendingUp, FileText, Lightbulb, Copy, Edit2, Check, Download, RotateCcw } from 'lucide-react';
import { ChatMessage } from '../types/chat';
import ContentButton from './ContentButton';
import VisualizationModal from './VisualizationModal';
import InsightsModal from './InsightsModal';
import PolicyModal from './PolicyModal';
import ReportModal from './ReportModal';

interface MessageBubbleProps {
  message: ChatMessage;
  onEdit?: (messageId: string, newContent: string) => void;
  onRegenerate?: (messageId: string) => void;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onEdit, onRegenerate }) => {
  const isAI = message.sender === 'ai';
  
  // Modal states
  const [isVizModalOpen, setIsVizModalOpen] = useState(false);
  const [isInsightsModalOpen, setIsInsightsModalOpen] = useState(false);
  const [isPolicyModalOpen, setIsPolicyModalOpen] = useState(false);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  
  // Copy & Edit states
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(message.content);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  const formatTime = (date: Date | string | undefined | null): string => {
    if (!date) return '';
    
    try {
      const dateObj = typeof date === 'string' ? new Date(date) : date;
      if (isNaN(dateObj.getTime())) return '';
      return dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };
  
  // Auto-resize textarea when editing
  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [isEditing, editedContent]);

  // Reset edited content when message changes
  useEffect(() => {
    setEditedContent(message.content);
  }, [message.content]);
  
  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  const handleStartEdit = () => {
    setEditedContent(message.content);
    setIsEditing(true);
  };

  const handleSaveEdit = () => {
    if (onEdit && editedContent.trim() !== message.content) {
      onEdit(message.id, editedContent.trim());
    }
    setIsEditing(false);
  };
  
  const handleCancelEdit = () => {
    setEditedContent(message.content);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSaveEdit();
    }
    if (e.key === 'Escape') {
      handleCancelEdit();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEditedContent(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${e.target.scrollHeight}px`;
  };

  // ============================================
  // FIX: Helper functions to safely check arrays
  // This prevents rendering "0" when backend sends 0 instead of []
  // ============================================
  
  const getArrayLength = (arr: unknown): number => {
    if (Array.isArray(arr)) {
      return arr.length;
    }
    return 0;
  };

  const hasValidArray = (arr: unknown): boolean => {
    return Array.isArray(arr) && arr.length > 0;
  };

  // Safe getters for arrays
  const visualizationsCount = getArrayLength(message.visualizations);
  const insightsCount = getArrayLength(message.insights);
  const policiesCount = getArrayLength(message.policies);

  // Check if has any content
  const hasVisualizations = visualizationsCount > 0;
  const hasInsights = insightsCount > 0;
  const hasPolicies = policiesCount > 0;
  const hasAnyAnalysis = hasVisualizations || hasInsights || hasPolicies;

  // Get timestamp safely
  const timestamp = formatTime(message.timestamp);

  return (
    <div className={`flex gap-4 ${isAI ? 'flex-row' : 'flex-row-reverse'}`}>
      {/* Avatar */}
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
        isAI 
          ? 'bg-gradient-to-br from-red-500 to-orange-600' 
          : 'bg-gradient-to-br from-orange-400 to-red-500'
      }`}>
        {isAI ? (
          <Bot className="h-4 w-4 text-white" />
        ) : (
          <User className="h-4 w-4 text-white" />
        )}
      </div>

      {/* Message Content */}
      <div className={`flex-1 ${isAI ? '' : 'flex flex-col items-end'}`}>
        {/* Main Message with Copy/Edit buttons */}
        <div className="group relative">
          <div className={`${
            isAI 
              ? 'bg-transparent' 
              : isEditing 
                ? 'bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-2xl shadow-sm'
                : 'bg-gradient-to-r from-red-500 to-orange-600 text-white px-5 py-3 rounded-2xl shadow-sm'
          }`}>
            {isEditing ? (
              /* Claude-style Edit Mode */
              <div className="p-1">
                <textarea
                  ref={textareaRef}
                  value={editedContent}
                  onChange={handleTextareaChange}
                  onKeyDown={handleKeyDown}
                  className="w-full px-4 py-3 bg-transparent text-gray-900 dark:text-white text-[15px] leading-relaxed resize-none focus:outline-none min-h-[60px]"
                  placeholder="Type your message..."
                  autoFocus
                />
                
                {/* Edit Action Buttons */}
                <div className="flex items-center justify-between px-3 py-2 border-t border-gray-200 dark:border-gray-700">
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    <kbd className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-[10px]">⌘/Ctrl</kbd>
                    <span className="mx-1">+</span>
                    <kbd className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-[10px]">Enter</kbd>
                    <span className="ml-1">to save</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleCancelEdit}
                      className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSaveEdit}
                      disabled={!editedContent.trim()}
                      className="px-4 py-1.5 bg-gradient-to-r from-red-500 to-orange-600 hover:from-red-600 hover:to-orange-700 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Save & Submit
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              /* Normal Display Mode */
              <>
                <div className={`whitespace-pre-wrap text-[15px] leading-relaxed ${isAI ? 'text-gray-800 dark:text-gray-200' : 'text-white'}`}>
                  {message.content}
                </div>
                {/* Only show timestamp if valid */}
                {timestamp ? (
                  <div className={`text-xs mt-2 ${isAI ? 'text-gray-500 dark:text-gray-400' : 'text-red-100'}`}>
                    {timestamp}
                  </div>
                ) : null}
              </>
            )}
          </div>
          
          {/* Action Buttons - Show on hover */}
          {!isEditing && (
            <div className={`absolute top-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity ${
              isAI ? '-right-20' : '-left-20'
            }`}>
              <button
                onClick={handleCopy}
                className="p-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors shadow-sm"
                title="Copy message"
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-green-600" />
                ) : (
                  <Copy className="h-3.5 w-3.5 text-gray-600 dark:text-gray-300" />
                )}
              </button>
              
              {!isAI && onEdit && (
                <button
                  onClick={handleStartEdit}
                  className="p-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors shadow-sm"
                  title="Edit message"
                >
                  <Edit2 className="h-3.5 w-3.5 text-gray-600 dark:text-gray-300" />
                </button>
              )}

              {isAI && onRegenerate && (
                <button
                  onClick={() => onRegenerate(message.id)}
                  className="p-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors shadow-sm"
                  title="Regenerate response"
                >
                  <RotateCcw className="h-3.5 w-3.5 text-gray-600 dark:text-gray-300" />
                </button>
              )}
            </div>
          )}
        </div>

        {/* Content Buttons - Only render if array has items */}
        {hasVisualizations ? (
          <ContentButton
            icon={TrendingUp}
            title="Data Visualizations"
            count={visualizationsCount}
            itemLabel="chart"
            onClick={() => setIsVizModalOpen(true)}
          />
        ) : null}

        {hasInsights ? (
          <ContentButton
            icon={Lightbulb}
            title="Key Insights"
            count={insightsCount}
            itemLabel="insight"
            onClick={() => setIsInsightsModalOpen(true)}
          />
        ) : null}

        {hasPolicies ? (
          <ContentButton
            icon={FileText}
            title="Policy Recommendations"
            count={policiesCount}
            itemLabel="recommendation"
            onClick={() => setIsPolicyModalOpen(true)}
          />
        ) : null}
        
        {/* Report Button - Only if AI message with analysis */}
        {isAI && message.session_id && hasAnyAnalysis ? (
          <ContentButton
            icon={Download}
            title="Unduh Laporan Lengkap"
            count={1}
            itemLabel="report"
            onClick={() => setIsReportModalOpen(true)}
          />
        ) : null}
      </div>

      {/* Modals */}
      <VisualizationModal
        isOpen={isVizModalOpen}
        onClose={() => setIsVizModalOpen(false)}
        visualizations={Array.isArray(message.visualizations) ? message.visualizations : []}
      />
      
      <InsightsModal
        isOpen={isInsightsModalOpen}
        onClose={() => setIsInsightsModalOpen(false)}
        insights={Array.isArray(message.insights) ? message.insights : []}
      />
      
      <PolicyModal
        isOpen={isPolicyModalOpen}
        onClose={() => setIsPolicyModalOpen(false)}
        policies={Array.isArray(message.policies) ? message.policies : []}
      />
      
      <ReportModal
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
        message={message}
        sessionId={message.session_id!}
      />
    </div>
  );
};

export default MessageBubble;