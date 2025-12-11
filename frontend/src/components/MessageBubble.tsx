import React, { useState, useRef, useEffect } from 'react';
import { Bot, User, TrendingUp, FileText, Lightbulb, Copy, Edit2, Check, Download, X, RotateCcw } from 'lucide-react';
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
  
  const formatTime = (date: Date | string) => {
    try {
      const dateObj = typeof date === 'string' ? new Date(date) : date;
      return dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (error) {
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
    // Save on Cmd/Ctrl + Enter
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSaveEdit();
    }
    // Cancel on Escape
    if (e.key === 'Escape') {
      handleCancelEdit();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEditedContent(e.target.value);
    // Auto-resize
    e.target.style.height = 'auto';
    e.target.style.height = `${e.target.scrollHeight}px`;
  };

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
                
                {/* Edit Action Buttons - Claude style */}
                <div className="flex items-center justify-between px-3 py-2 border-t border-gray-200 dark:border-gray-700">
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    <kbd className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-[10px]">⌘</kbd>
                    <span className="mx-1">+</span>
                    <kbd className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-[10px]">Enter (for Mac OS)</kbd>
                    <span className="mx-1">or</span>
                    <kbd className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-[10px]">ctrl</kbd>
                    <span className="mx-1">+</span>
                    <kbd className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-[10px]">Enter (for Windows)</kbd>
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
                <div className={`text-xs mt-2 ${isAI ? 'text-gray-500 dark:text-gray-400' : 'text-red-100'}`}>
                  {formatTime(message.timestamp)}
                </div>
              </>
            )}
          </div>
          
          {/* Action Buttons - Show on hover (only when not editing) */}
          {!isEditing && (
            <div className={`absolute top-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity ${
              isAI ? '-right-20' : '-left-20'
            }`}>
              {/* Copy Button */}
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
              
              {/* Edit Button - Only for user messages */}
              {!isAI && onEdit && (
                <button
                  onClick={handleStartEdit}
                  className="p-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors shadow-sm"
                  title="Edit message"
                >
                  <Edit2 className="h-3.5 w-3.5 text-gray-600 dark:text-gray-300" />
                </button>
              )}

              {/* Regenerate Button - Only for AI messages */}
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

        {/* Visualizations Button */}
        {message.visualizations && message.visualizations.length > 0 && (
          <ContentButton
            icon={TrendingUp}
            title="Data Visualizations"
            count={message.visualizations.length}
            itemLabel="chart"
            onClick={() => setIsVizModalOpen(true)}
          />
        )}

        {/* Insights Button */}
        {message.insights && message.insights.length > 0 && (
          <ContentButton
            icon={Lightbulb}
            title="Key Insights"
            count={message.insights.length}
            itemLabel="insight"
            onClick={() => setIsInsightsModalOpen(true)}
          />
        )}

        {/* Policy Recommendations Button */}
        {message.policies && message.policies.length > 0 && (
          <ContentButton
            icon={FileText}
            title="Policy Recommendations"
            count={message.policies.length}
            itemLabel="recommendation"
            onClick={() => setIsPolicyModalOpen(true)}
          />
        )}
        
        {/* Report Download Button - Only for AI messages with analysis */}
        {isAI && message.session_id && (message.visualizations?.length || message.insights?.length || message.policies?.length) && (
          <ContentButton
            icon={Download}
            title="Unduh Laporan Lengkap"
            count={1}
            itemLabel="report"
            onClick={() => setIsReportModalOpen(true)}
          />
        )}
      </div>

      {/* Modals */}
      <VisualizationModal
        isOpen={isVizModalOpen}
        onClose={() => setIsVizModalOpen(false)}
        visualizations={message.visualizations || []}
      />
      
      <InsightsModal
        isOpen={isInsightsModalOpen}
        onClose={() => setIsInsightsModalOpen(false)}
        insights={message.insights || []}
      />
      
      <PolicyModal
        isOpen={isPolicyModalOpen}
        onClose={() => setIsPolicyModalOpen(false)}
        policies={message.policies || []}
      />
      
      <ReportModal
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
        message={message}
      />
    </div>
  );
};

export default MessageBubble;