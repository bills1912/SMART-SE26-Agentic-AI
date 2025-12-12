import React from 'react';
import { Lightbulb } from 'lucide-react';

interface InsightsPanelProps {
  insights: string[];
}

const InsightsPanel: React.FC<InsightsPanelProps> = ({ insights }) => {
  if (!insights || insights.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <p>Tidak ada insight untuk ditampilkan.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {insights.map((insight, index) => (
        <div
          key={index}
          className="bg-gray-700 rounded-xl p-4 flex gap-4"
        >
          <div className="flex-shrink-0">
            <div className="w-10 h-10 rounded-full bg-yellow-600/20 flex items-center justify-center">
              <Lightbulb className="w-5 h-5 text-yellow-500" />
            </div>
          </div>
          <div className="flex-1">
            <div className="text-sm text-yellow-400 font-medium mb-1">
              Insight #{index + 1}
            </div>
            <p className="text-gray-200">{insight}</p>
          </div>
        </div>
      ))}
    </div>
  );
};

export default InsightsPanel;
