import React from 'react';
import { Card } from './ui/card';
import { Lightbulb } from 'lucide-react';

interface InsightCardProps {
  insight: string;
}

const InsightCard: React.FC<InsightCardProps> = ({ insight }) => {
  return (
    <Card className="p-4 bg-gradient-to-r from-orange-50 to-red-50 border-orange-200 shadow-sm hover:shadow-md transition-all duration-200">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 bg-gradient-to-br from-red-500 to-orange-600 rounded-lg flex items-center justify-center flex-shrink-0">
          <Lightbulb className="h-4 w-4 text-white" />
        </div>
        <p className="text-sm text-gray-700 leading-relaxed">{insight}</p>
      </div>
    </Card>
  );
};

export default InsightCard;