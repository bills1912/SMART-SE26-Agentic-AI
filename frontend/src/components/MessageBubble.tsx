import React from 'react';
import { Bot, User, TrendingUp, FileText, Lightbulb } from 'lucide-react';
import { ChatMessage } from '../types/chat';
import VisualizationComponent from './VisualizationComponent';
import PolicyCard from './PolicyCard';
import InsightCard from './InsightCard';

interface MessageBubbleProps {
  message: ChatMessage;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isAI = message.sender === 'ai';
  
  const formatTime = (date: Date | string) => {
    try {
      const dateObj = typeof date === 'string' ? new Date(date) : date;
      return dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (error) {
      return 'Unknown time';
    }
  };

  return (
    <div className={`flex gap-3 ${isAI ? 'flex-row' : 'flex-row-reverse'}`}>
      {/* Avatar */}
      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
        isAI 
          ? 'bg-gradient-to-br from-red-500 to-orange-600' 
          : 'bg-gradient-to-br from-orange-400 to-red-500'
      }`}>
        {isAI ? (
          <Bot className="h-5 w-5 text-white" />
        ) : (
          <User className="h-5 w-5 text-white" />
        )}
      </div>

      {/* Message Content */}
      <div className={`flex-1 max-w-4xl ${isAI ? '' : 'flex flex-col items-end'}`}>
        {/* Main Message */}
        <div className={`p-4 rounded-xl border ${
          isAI 
            ? 'bg-white dark:bg-gray-700 border-orange-200 dark:border-gray-600 shadow-md' 
            : 'bg-gradient-to-r from-red-500 to-orange-600 text-white border-none shadow-lg'
        }`}>
          <div className={`whitespace-pre-wrap text-sm leading-relaxed ${isAI ? 'text-gray-800 dark:text-gray-200' : 'text-white'}`}>
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