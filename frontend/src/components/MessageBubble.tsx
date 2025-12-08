import React, { useState } from 'react';
import { Bot, User, TrendingUp, FileText, Lightbulb } from 'lucide-react';
import { ChatMessage } from '../types/chat';
import ContentButton from './ContentButton';
import VisualizationModal from './VisualizationModal';
import InsightsModal from './InsightsModal';
import PolicyModal from './PolicyModal';

interface MessageBubbleProps {
  message: ChatMessage;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isAI = message.sender === 'ai';
  
  // Modal states
  const [isVizModalOpen, setIsVizModalOpen] = useState(false);
  const [isInsightsModalOpen, setIsInsightsModalOpen] = useState(false);
  const [isPolicyModalOpen, setIsPolicyModalOpen] = useState(false);
  
  const formatTime = (date: Date | string) => {
    try {
      const dateObj = typeof date === 'string' ? new Date(date) : date;
      return dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (error) {
      return 'Unknown time';
    }
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

        {/* Visualizations */}
        {message.visualizations && message.visualizations.length > 0 && (
          <div className="mt-4 space-y-4">
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400 font-medium">
              <TrendingUp className="h-4 w-4" />
              <span>Data Visualizations</span>
            </div>
            <div className="grid gap-4">
              {message.visualizations.map((viz) => (
                <VisualizationComponent key={viz.id} visualization={viz} />
              ))}
            </div>
          </div>
        )}

        {/* Insights */}
        {message.insights && message.insights.length > 0 && (
          <div className="mt-4 space-y-3">
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400 font-medium">
              <Lightbulb className="h-4 w-4" />
              <span>Key Insights</span>
            </div>
            <div className="space-y-2">
              {message.insights.map((insight, index) => (
                <InsightCard key={index} insight={insight} />
              ))}
            </div>
          </div>
        )}

        {/* Policy Recommendations */}
        {message.policies && message.policies.length > 0 && (
          <div className="mt-4 space-y-3">
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400 font-medium">
              <FileText className="h-4 w-4" />
              <span>Policy Recommendations</span>
            </div>
            <div className="space-y-3">
              {message.policies.map((policy) => (
                <PolicyCard key={policy.id} policy={policy} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MessageBubble;