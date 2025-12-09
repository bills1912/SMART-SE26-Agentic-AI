import React, { useState } from 'react';
import { X, FileText, Download, Loader2 } from 'lucide-react';
import apiService from '../services/api';

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string;
  messageContent: string;
}

const ReportModal: React.FC<ReportModalProps> = ({ 
  isOpen, 
  onClose, 
  sessionId,
  messageContent
}) => {
  const [generating, setGenerating] = useState(false);
  const [generatingFormat, setGeneratingFormat] = useState<'pdf' | 'docx' | null>(null);

  if (!isOpen) return null;

  const handleDownload = async (format: 'pdf' | 'docx') => {
    try {
      setGenerating(true);
      setGeneratingFormat(format);
      
      // Call API to generate report
      const response = await apiService.generateReport(sessionId, format);
      
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
      setGenerating(false);
      setGeneratingFormat(null);
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
          className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden pointer-events-auto animate-in zoom-in-95 duration-200"
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
                  Unduh Laporan Analisis
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Pilih format laporan yang ingin diunduh
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
          <div className="p-6 space-y-4">
            {/* Preview Info */}
            <div className="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                Isi Laporan:
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-3">
                {messageContent}
              </p>
            </div>

            {/* Download Options */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                Pilih Format:
              </h3>
              
              {/* PDF Option */}
              <button
                onClick={() => handleDownload('pdf')}
                disabled={generating}
                className="w-full flex items-center justify-between p-4 bg-white dark:bg-gray-700 border-2 border-gray-200 dark:border-gray-600 hover:border-orange-500 dark:hover:border-orange-500 rounded-xl transition-all duration-200 hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="flex items-center gap-3">
                  <FileText className="h-6 w-6 text-red-600" />
                  <div className="text-left">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">
                      Format PDF
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      Portable Document Format
                    </div>
                  </div>
                </div>
                {generating && generatingFormat === 'pdf' ? (
                  <Loader2 className="h-5 w-5 animate-spin text-orange-600" />
                ) : (
                  <Download className="h-5 w-5 text-gray-400" />
                )}
              </button>

              {/* DOCX Option */}
              <button
                onClick={() => handleDownload('docx')}
                disabled={generating}
                className="w-full flex items-center justify-between p-4 bg-white dark:bg-gray-700 border-2 border-gray-200 dark:border-gray-600 hover:border-orange-500 dark:hover:border-orange-500 rounded-xl transition-all duration-200 hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="flex items-center gap-3">
                  <FileText className="h-6 w-6 text-blue-600" />
                  <div className="text-left">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">
                      Format Word
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      Microsoft Word Document (.docx)
                    </div>
                  </div>
                </div>
                {generating && generatingFormat === 'docx' ? (
                  <Loader2 className="h-5 w-5 animate-spin text-orange-600" />
                ) : (
                  <Download className="h-5 w-5 text-gray-400" />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default ReportModal;
