import React, { useState } from 'react';
import { Bot, User, TrendingUp, FileText, Lightbulb, Copy, Edit2, Check } from 'lucide-react';
import { ChatMessage } from '../types/chat';
import ContentButton from './ContentButton';
import VisualizationModal from './VisualizationModal';
import InsightsModal from './InsightsModal';
import PolicyModal from './PolicyModal';

interface MessageBubbleProps {
  message: ChatMessage;
  onEdit?: (messageId: string, newContent: string) => void;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onEdit }) => {
  const isAI = message.sender === 'ai';
  
  // Modal states
  const [isVizModalOpen, setIsVizModalOpen] = useState(false);
  const [isInsightsModalOpen, setIsInsightsModalOpen] = useState(false);
  const [isPolicyModalOpen, setIsPolicyModalOpen] = useState(false);
  
  // Copy & Edit states
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(message.content);
  
  const formatTime = (date: Date | string) => {
    try {
      const dateObj = typeof date === 'string' ? new Date(date) : date;
      return dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (error) {
      return 'Unknown time';
    }
  };
  
  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  const handleEdit = () => {
    if (isEditing && onEdit) {
      onEdit(message.id, editedContent);
      setIsEditing(false);
    } else {
      setIsEditing(true);
    }
  };
  
  const handleCancelEdit = () => {
    setEditedContent(message.content);
    setIsEditing(false);
  };

  return (
    <div className={`flex gap-4 ${isAI ? 'flex-row' : 'flex-row-reverse'}`}>
      {/* Avatar - Slightly larger for prominence */}
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
        isAI 
          ? 'bg-gradient-to-br from-red-500 to-orange-600' 
          : 'bg-gradient-to-br from-orange-400 to-red-500'
      }`}>
        {isAI ? (
          <Bot className="h-4.5 w-4.5 text-white" />
        ) : (
          <User className="h-4.5 w-4.5 text-white" />
        )}
      </div>

      {/* Message Content - Full width for better readability */}
      <div className={`flex-1 ${isAI ? '' : 'flex flex-col items-end'}`}>
        {/* Main Message - Removed borders for cleaner look */}
        <div className={`${
          isAI 
            ? 'bg-transparent' 
            : 'bg-gradient-to-r from-red-500 to-orange-600 text-white px-5 py-3 rounded-2xl shadow-sm'
        }`}>
          <div className={`whitespace-pre-wrap text-[15px] leading-relaxed ${isAI ? 'text-gray-800 dark:text-gray-200' : 'text-white'}`}>
            {message.content}
          </div>
          <div className={`text-xs mt-2 ${isAI ? 'text-gray-500 dark:text-gray-400' : 'text-red-100'}`}>
            {formatTime(message.timestamp)}
          </div>
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
    </div>
  );
};

export default MessageBubble;