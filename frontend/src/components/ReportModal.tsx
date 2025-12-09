import React, { useState, useEffect } from 'react';
import { X, Download, Loader2, FileText } from 'lucide-react';
import apiService from '../services/api';

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  message: any;
}

const ReportModal: React.FC<ReportModalProps> = ({ 
  isOpen, 
  onClose, 
  message
}) => {
  const [downloading, setDownloading] = useState(false);
  const [downloadingFormat, setDownloadingFormat] = useState<'pdf' | 'docx' | null>(null);

  if (!isOpen) return null;

  const handleDownload = async (format: 'pdf' | 'docx') => {
    try {
      setDownloading(true);
      setDownloadingFormat(format);
      
      // Call API to generate report
      const response = await apiService.generateReport(message.session_id, format);
      
      // Create download link
      const blob = new Blob([response.data], { 
        type: format === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' 
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Laporan_Analisis_Sensus_${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error('Failed to generate report:', error);
      alert('Gagal menghasilkan laporan. Silakan coba lagi.');
    } finally {
      setDownloading(false);
      setDownloadingFormat(null);
    }
  };

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
          {/* Header with Download Buttons */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-red-500 to-orange-600 rounded-lg flex items-center justify-center">
                <FileText className="h-5 w-5 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                  Laporan Analisis Lengkap
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Preview dan unduh laporan
                </p>
              </div>
            </div>
            
            {/* Download Buttons - Small in corner */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleDownload('pdf')}
                disabled={downloading}
                className="flex items-center gap-2 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
                title="Download PDF"
              >
                {downloading && downloadingFormat === 'pdf' ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                <span>PDF</span>
              </button>
              
              <button
                onClick={() => handleDownload('docx')}
                disabled={downloading}
                className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
                title="Download Word"
              >
                {downloading && downloadingFormat === 'docx' ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                <span>Word</span>
              </button>
              
              <button
                onClick={onClose}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                aria-label="Close modal"
              >
                <X className="h-5 w-5 text-gray-500 dark:text-gray-400" />
              </button>
            </div>
          </div>

          {/* Report Preview */}
          <div className="overflow-y-auto max-h-[calc(85vh-80px)] p-8 bg-gray-50 dark:bg-gray-900">
            <div className="max-w-3xl mx-auto bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8">
              {/* Report Header */}
              <div className="text-center mb-8 pb-6 border-b-2 border-orange-500">
                <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
                  Laporan Analisis Sensus Ekonomi Indonesia
                </h1>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {new Date().toLocaleDateString('id-ID', { 
                    weekday: 'long', 
                    year: 'numeric', 
                    month: 'long', 
                    day: 'numeric' 
                  })}
                </p>
              </div>

              {/* Main Content */}
              <div className="space-y-6">
                <div className="prose dark:prose-invert max-w-none">
                  <h2 className="text-xl font-semibold text-orange-600 dark:text-orange-400 mb-3">
                    Analisis
                  </h2>
                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                    <p className="text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                      {message.content}
                    </p>
                  </div>
                </div>

                {/* Insights Section */}
                {message.insights && message.insights.length > 0 && (
                  <div>
                    <h2 className="text-xl font-semibold text-orange-600 dark:text-orange-400 mb-3">
                      Key Insights
                    </h2>
                    <div className="space-y-2">
                      {message.insights.map((insight: string, index: number) => (
                        <div 
                          key={index}
                          className="flex gap-3 p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg border border-orange-200 dark:border-orange-700"
                        >
                          <div className="flex-shrink-0 w-6 h-6 bg-orange-600 text-white rounded-full flex items-center justify-center text-xs font-bold">
                            {index + 1}
                          </div>
                          <p className="text-gray-700 dark:text-gray-300 text-sm">
                            {insight}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Policy Recommendations */}
                {message.policies && message.policies.length > 0 && (
                  <div>
                    <h2 className="text-xl font-semibold text-orange-600 dark:text-orange-400 mb-3">
                      Rekomendasi Kebijakan
                    </h2>
                    <div className="space-y-4">
                      {message.policies.map((policy: any) => (
                        <div 
                          key={policy.id}
                          className="border-l-4 border-orange-500 bg-gray-50 dark:bg-gray-900 rounded-r-lg p-4"
                        >
                          <div className="flex items-start gap-2 mb-2">
                            <span className={`px-2 py-1 text-xs font-semibold rounded ${
                              policy.priority === 'high' ? 'bg-red-100 text-red-800' :
                              policy.priority === 'medium' ? 'bg-orange-100 text-orange-800' :
                              'bg-green-100 text-green-800'
                            }`}>
                              {policy.priority.toUpperCase()}
                            </span>
                            <span className="px-2 py-1 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">
                              {policy.category}
                            </span>
                          </div>
                          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-2">
                            {policy.title}
                          </h3>
                          <p className="text-sm text-gray-700 dark:text-gray-300 mb-3">
                            {policy.description}
                          </p>
                          <div className="bg-orange-50 dark:bg-orange-900/20 rounded p-3">
                            <p className="text-xs font-semibold text-orange-800 dark:text-orange-300 mb-1">
                              Expected Impact:
                            </p>
                            <p className="text-sm text-orange-700 dark:text-orange-200">
                              {policy.impact}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Visualizations Info */}
                {message.visualizations && message.visualizations.length > 0 && (
                  <div>
                    <h2 className="text-xl font-semibold text-orange-600 dark:text-orange-400 mb-3">
                      Data Visualizations
                    </h2>
                    <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
                      <p className="text-sm text-blue-700 dark:text-blue-300">
                        📊 Laporan ini mencakup {message.visualizations.length} visualisasi data.
                        Grafik dan chart dapat dilihat pada tampilan interactive di aplikasi.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 text-center">
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Laporan ini dibuat secara otomatis oleh AI Policy & Insight Generator
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                  © {new Date().getFullYear()} Sensus Ekonomi Indonesia
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default ReportModal;
