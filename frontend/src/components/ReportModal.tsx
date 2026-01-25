import React, { useState } from 'react';
import { X, Download, Loader2, FileText, Globe } from 'lucide-react';
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
  const [downloadingFormat, setDownloadingFormat] = useState<'pdf' | 'docx' | 'html' | null>(null);

  if (!isOpen) return null;

  const handleDownload = async (format: 'pdf' | 'docx' | 'html') => {
    try {
      setDownloading(true);
      setDownloadingFormat(format);
      
      // Call API to generate report
      const response = await apiService.generateReport(message.session_id, format);
      
      // Determine MIME type
      let mimeType = 'application/octet-stream';
      if (format === 'pdf') {
        mimeType = 'application/pdf';
      } else if (format === 'docx') {
        mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      } else if (format === 'html') {
        mimeType = 'text/html';
      }
      
      // Create download link
      const blob = new Blob([response.data], { type: mimeType });
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

  // Count items safely
  const vizCount = Array.isArray(message.visualizations) ? message.visualizations.length : 0;
  const insightCount = Array.isArray(message.insights) ? message.insights.length : 0;
  const policyCount = Array.isArray(message.policies) ? message.policies.length : 0;

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
            
            {/* Download Buttons */}
            <div className="flex items-center gap-2">
              {/* PDF Button */}
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
              
              {/* Word Button */}
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
              
              {/* HTML Button */}
              <button
                onClick={() => handleDownload('html')}
                disabled={downloading}
                className="flex items-center gap-2 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
                title="Download HTML (dengan chart interaktif)"
              >
                {downloading && downloadingFormat === 'html' ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Globe className="h-4 w-4" />
                )}
                <span>HTML</span>
              </button>
              
              <button
                onClick={onClose}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors ml-2"
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

              {/* Summary Stats */}
              <div className="grid grid-cols-3 gap-4 mb-8">
                <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{vizCount}</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Visualisasi</div>
                </div>
                <div className="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">{insightCount}</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Insights</div>
                </div>
                <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-green-600 dark:text-green-400">{policyCount}</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Rekomendasi</div>
                </div>
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

                {/* Visualizations Info */}
                {vizCount > 0 && (
                  <div>
                    <h2 className="text-xl font-semibold text-orange-600 dark:text-orange-400 mb-3">
                      📊 Data Visualisasi
                    </h2>
                    <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
                      <p className="text-sm text-blue-700 dark:text-blue-300 mb-3">
                        Laporan ini mencakup {vizCount} visualisasi data. Untuk melihat grafik interaktif, 
                        <strong> unduh versi HTML</strong>.
                      </p>
                      <div className="space-y-2">
                        {message.visualizations.map((viz: any, index: number) => (
                          <div key={index} className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                            <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-xs font-bold">
                              {index + 1}
                            </span>
                            <span>{viz.title || `Visualisasi ${index + 1}`}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Insights Section */}
                {insightCount > 0 && (
                  <div>
                    <h2 className="text-xl font-semibold text-orange-600 dark:text-orange-400 mb-3">
                      💡 Key Insights
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
                {policyCount > 0 && (
                  <div>
                    <h2 className="text-xl font-semibold text-orange-600 dark:text-orange-400 mb-3">
                      🎯 Rekomendasi Kebijakan
                    </h2>
                    <div className="space-y-4">
                      {message.policies.map((policy: any, index: number) => (
                        <div 
                          key={policy.id || index}
                          className="border-l-4 border-orange-500 bg-gray-50 dark:bg-gray-900 rounded-r-lg p-4"
                        >
                          <div className="flex items-start gap-2 mb-2">
                            <span className={`px-2 py-1 text-xs font-semibold rounded ${
                              policy.priority === 'high' ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400' :
                              policy.priority === 'medium' ? 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400' :
                              'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                            }`}>
                              {policy.priority?.toUpperCase() || 'MEDIUM'}
                            </span>
                            <span className="px-2 py-1 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">
                              {policy.category || 'Kebijakan'}
                            </span>
                          </div>
                          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-2">
                            {policy.title}
                          </h3>
                          <p className="text-sm text-gray-700 dark:text-gray-300 mb-3">
                            {policy.description}
                          </p>
                          {policy.impact && (
                            <div className="bg-orange-50 dark:bg-orange-900/20 rounded p-3">
                              <p className="text-xs font-semibold text-orange-800 dark:text-orange-300 mb-1">
                                Expected Impact:
                              </p>
                              <p className="text-sm text-orange-700 dark:text-orange-200">
                                {policy.impact}
                              </p>
                            </div>
                          )}
                          {policy.implementation_steps && policy.implementation_steps.length > 0 && (
                            <div className="mt-3">
                              <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
                                Langkah Implementasi:
                              </p>
                              <ol className="list-decimal list-inside text-sm text-gray-600 dark:text-gray-400 space-y-1">
                                {policy.implementation_steps.map((step: string, stepIndex: number) => (
                                  <li key={stepIndex}>{step}</li>
                                ))}
                              </ol>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Download Reminder */}
              <div className="mt-8 p-4 bg-gradient-to-r from-orange-50 to-red-50 dark:from-orange-900/20 dark:to-red-900/20 rounded-lg border border-orange-200 dark:border-orange-700">
                <p className="text-sm text-gray-700 dark:text-gray-300 text-center">
                  💡 <strong>Tips:</strong> Unduh versi <strong>HTML</strong> untuk mendapatkan laporan dengan grafik interaktif yang dapat di-zoom dan di-hover.
                  Versi <strong>PDF</strong> dan <strong>Word</strong> menyertakan tabel data dari setiap visualisasi.
                </p>
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