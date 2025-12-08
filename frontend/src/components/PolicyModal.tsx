import React from 'react';
import { X, FileText } from 'lucide-react';
import PolicyCard from './PolicyCard';

interface PolicyRecommendation {
  id: string;
  title: string;
  description: string;
  priority: string;
  category: string;
  expectedImpact: string;
  implementationSteps: string[];
}

interface PolicyModalProps {
  isOpen: boolean;
  onClose: () => void;
  policies: PolicyRecommendation[];
}

const PolicyModal: React.FC<PolicyModalProps> = ({ 
  isOpen, 
  onClose, 
  policies
}) => {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in fade-in duration-200"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div 
          className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-hidden pointer-events-auto animate-in zoom-in-95 duration-200"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-red-500 to-orange-600 rounded-lg flex items-center justify-center">
                <FileText className="h-5 w-5 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                  Policy Recommendations
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {policies.length} {policies.length === 1 ? 'recommendation' : 'recommendations'} available
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              aria-label="Close modal"
            >
              <X className="h-5 w-5 text-gray-500 dark:text-gray-400" />
            </button>
          </div>

          {/* Content */}
          <div className="overflow-y-auto max-h-[calc(85vh-80px)] p-6">
            <div className="space-y-4">
              {policies.map((policy) => (
                <PolicyCard key={policy.id} policy={policy} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default PolicyModal;
