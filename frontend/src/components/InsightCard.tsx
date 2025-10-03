import React from 'react';
import { Lightbulb } from 'lucide-react';

interface InsightCardProps {
  insight: string;
}

const InsightCard: React.FC<InsightCardProps> = ({ insight }) => {
  return (
    <div className="p-4 bg-gradient-to-r from-orange-50 to-red-50 dark:from-gray-700 dark:to-gray-800 border border-orange-200 dark:border-gray-600 shadow-sm hover:shadow-md transition-all duration-200 rounded-xl">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 bg-gradient-to-br from-red-500 to-orange-600 rounded-lg flex items-center justify-center flex-shrink-0">
          <Lightbulb className="h-4 w-4 text-white" />
        </div>
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{insight}</p>
      </div>
    </div>
  );
};

export default InsightCard;