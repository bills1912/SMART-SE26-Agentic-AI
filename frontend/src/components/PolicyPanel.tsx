import React from 'react';
import { FileText, AlertCircle, CheckCircle, Clock } from 'lucide-react';

interface PolicyRecommendation {
  id?: string;
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  category?: string;
  impact?: string;
  implementation_steps?: string[];
}

interface PolicyPanelProps {
  policies: PolicyRecommendation[];
}

const PolicyPanel: React.FC<PolicyPanelProps> = ({ policies }) => {
  if (!policies || policies.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <p>Tidak ada rekomendasi kebijakan untuk ditampilkan.</p>
      </div>
    );
  }

  const getPriorityConfig = (priority: string) => {
    switch (priority) {
      case 'high':
        return {
          icon: AlertCircle,
          color: 'text-red-500',
          bg: 'bg-red-500/20',
          label: 'Prioritas Tinggi',
          border: 'border-red-500/30',
        };
      case 'medium':
        return {
          icon: Clock,
          color: 'text-yellow-500',
          bg: 'bg-yellow-500/20',
          label: 'Prioritas Menengah',
          border: 'border-yellow-500/30',
        };
      case 'low':
        return {
          icon: CheckCircle,
          color: 'text-green-500',
          bg: 'bg-green-500/20',
          label: 'Prioritas Rendah',
          border: 'border-green-500/30',
        };
      default:
        return {
          icon: FileText,
          color: 'text-gray-500',
          bg: 'bg-gray-500/20',
          label: 'Prioritas',
          border: 'border-gray-500/30',
        };
    }
  };

  return (
    <div className="space-y-6">
      {policies.map((policy, index) => {
        const priorityConfig = getPriorityConfig(policy.priority);
        const PriorityIcon = priorityConfig.icon;

        return (
          <div
            key={policy.id || index}
            className={`bg-gray-700 rounded-xl p-5 border ${priorityConfig.border}`}
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-white mb-1">
                  {index + 1}. {policy.title}
                </h3>
                <div className="flex items-center gap-3 flex-wrap">
                  <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs ${priorityConfig.bg} ${priorityConfig.color}`}>
                    <PriorityIcon className="w-3 h-3" />
                    {priorityConfig.label}
                  </span>
                  {policy.category && (
                    <span className="text-xs text-gray-400 bg-gray-600 px-2 py-1 rounded-full">
                      {policy.category}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Description */}
            <p className="text-gray-300 mb-4">{policy.description}</p>

            {/* Impact */}
            {policy.impact && (
              <div className="mb-4">
                <h4 className="text-sm font-medium text-orange-400 mb-1">Dampak:</h4>
                <p className="text-gray-300 text-sm">{policy.impact}</p>
              </div>
            )}

            {/* Implementation Steps */}
            {policy.implementation_steps && policy.implementation_steps.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-blue-400 mb-2">Langkah Implementasi:</h4>
                <ol className="list-decimal list-inside space-y-1">
                  {policy.implementation_steps.map((step, stepIndex) => (
                    <li key={stepIndex} className="text-gray-300 text-sm">
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default PolicyPanel;
