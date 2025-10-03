import React from 'react';
import { CheckCircle2, AlertCircle, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import { PolicyRecommendation } from '../types/chat';
import { useState } from 'react';

interface PolicyCardProps {
  policy: PolicyRecommendation;
}

const PolicyCard: React.FC<PolicyCardProps> = ({ policy }) => {
  const [expanded, setExpanded] = useState(false);

  const getPriorityIcon = (priority: string) => {
    switch (priority) {
      case 'high':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'medium':
        return <Clock className="h-4 w-4 text-orange-500" />;
      case 'low':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'medium':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'low':
        return 'bg-green-100 text-green-800 border-green-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="p-4 bg-white border border-orange-200 shadow-md hover:shadow-lg transition-all duration-200 rounded-xl">
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              {getPriorityIcon(policy.priority)}
              <h4 className="font-semibold text-gray-800">{policy.title}</h4>
              <div className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold ${getPriorityColor(policy.priority)}`}>
                {policy.priority.toUpperCase()} PRIORITY
              </div>
            </div>
            <div className="inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold text-foreground mb-2">
              {policy.category}
            </div>
          </div>
        </div>

        {/* Description */}
        <p className="text-sm text-gray-600">{policy.description}</p>

        {/* Impact */}
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
          <div className="text-xs font-medium text-orange-800 mb-1">Expected Impact</div>
          <div className="text-sm text-orange-700">{policy.impact}</div>
        </div>

        {/* Implementation Steps */}
        <div className="space-y-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center justify-between text-gray-600 hover:text-red-600 hover:bg-accent hover:text-accent-foreground h-8 rounded-md px-3 text-xs"
          >
            <span className="text-xs font-medium">Implementation Steps</span>
            {expanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>

          {expanded && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 space-y-2">
              {policy.implementation_steps.map((step, index) => (
                <div key={index} className="flex items-start gap-2">
                  <div className="w-5 h-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center flex-shrink-0 mt-0.5">
                    {index + 1}
                  </div>
                  <div className="text-sm text-gray-700">{step}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};

export default PolicyCard;