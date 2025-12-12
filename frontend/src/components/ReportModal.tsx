import React, { useState } from 'react';
import { X, FileText, FileSpreadsheet, Globe, Download, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import api from '../services/api';

type ReportFormat = 'pdf' | 'docx' | 'html';

interface MessageData {
  id: string;
  visualizations?: any[];
  insights?: string[];
  policies?: any[];
}

interface ReportModalProps {
  sessionId: string;
  onClose: () => void;
  messageData?: MessageData;
}

const ReportModal: React.FC<ReportModalProps> = ({ sessionId, onClose, messageData }) => {
  const [downloading, setDownloading] = useState<ReportFormat | null>(null);
  const [success, setSuccess] = useState<ReportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async (format: ReportFormat) => {
    setDownloading(format);
    setError(null);
    setSuccess(null);

    try {
      const response = await api.get(`/report/${sessionId}/${format}`, {
        responseType: 'blob',
        timeout: 180000, // 3 minutes for report generation
      });

      // Create download link
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Set filename based on format
      const extensions: Record<ReportFormat, string> = {
        pdf: 'pdf',
        docx: 'docx',
        html: 'html',
      };
      link.download = `Laporan_Sensus_Ekonomi_${sessionId.slice(0, 8)}.${extensions[format]}`;
      
      // Trigger download
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      setSuccess(format);
      
      // Clear success after 3 seconds
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      console.error('Download error:', err);
      setError(`Gagal mengunduh laporan ${format.toUpperCase()}. Silakan coba lagi.`);
    } finally {
      setDownloading(null);
    }
  };

  // Count data from messageData if available
  const vizCount = messageData?.visualizations?.length || 0;
  const insightCount = messageData?.insights?.length || 0;
  const policyCount = messageData?.policies?.length || 0;
  const hasData = vizCount > 0 || insightCount > 0 || policyCount > 0;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-gray-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-700">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Download className="w-5 h-5 text-orange-500" />
            Unduh Laporan
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4">
          {/* Summary Stats */}
          {hasData && (
            <div className="bg-gray-700/50 rounded-xl p-4">
              <h3 className="text-sm font-medium text-gray-300 mb-3">Konten Laporan:</h3>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="bg-gray-700 rounded-lg p-3">
                  <div className="text-2xl font-bold text-blue-400">{vizCount}</div>
                  <div className="text-xs text-gray-400">Visualisasi</div>
                </div>
                <div className="bg-gray-700 rounded-lg p-3">
                  <div className="text-2xl font-bold text-yellow-400">{insightCount}</div>
                  <div className="text-xs text-gray-400">Insights</div>
                </div>
                <div className="bg-gray-700 rounded-lg p-3">
                  <div className="text-2xl font-bold text-orange-400">{policyCount}</div>
                  <div className="text-xs text-gray-400">Kebijakan</div>
                </div>
              </div>
            </div>
          )}

          {/* Format Options */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-gray-300">Pilih Format:</h3>

            {/* PDF */}
            <button
              onClick={() => handleDownload('pdf')}
              disabled={downloading !== null}
              className="w-full flex items-center justify-between p-4 bg-red-600/20 hover:bg-red-600/30 border border-red-500/30 rounded-xl transition-all disabled:opacity-50"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-red-600 rounded-lg flex items-center justify-center">
                  <FileText className="w-5 h-5 text-white" />
                </div>
                <div className="text-left">
                  <div className="font-medium text-white">PDF Document</div>
                  <div className="text-xs text-gray-400">Format siap cetak dengan tabel data</div>
                </div>
              </div>
              {downloading === 'pdf' ? (
                <Loader2 className="w-5 h-5 text-red-400 animate-spin" />
              ) : success === 'pdf' ? (
                <CheckCircle className="w-5 h-5 text-green-400" />
              ) : (
                <Download className="w-5 h-5 text-red-400" />
              )}
            </button>

            {/* DOCX */}
            <button
              onClick={() => handleDownload('docx')}
              disabled={downloading !== null}
              className="w-full flex items-center justify-between p-4 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 rounded-xl transition-all disabled:opacity-50"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
                  <FileSpreadsheet className="w-5 h-5 text-white" />
                </div>
                <div className="text-left">
                  <div className="font-medium text-white">Word Document</div>
                  <div className="text-xs text-gray-400">Format .docx untuk editing</div>
                </div>
              </div>
              {downloading === 'docx' ? (
                <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
              ) : success === 'docx' ? (
                <CheckCircle className="w-5 h-5 text-green-400" />
              ) : (
                <Download className="w-5 h-5 text-blue-400" />
              )}
            </button>

            {/* HTML */}
            <button
              onClick={() => handleDownload('html')}
              disabled={downloading !== null}
              className="w-full flex items-center justify-between p-4 bg-green-600/20 hover:bg-green-600/30 border border-green-500/30 rounded-xl transition-all disabled:opacity-50"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-green-600 rounded-lg flex items-center justify-center">
                  <Globe className="w-5 h-5 text-white" />
                </div>
                <div className="text-left">
                  <div className="font-medium text-white">HTML Interactive</div>
                  <div className="text-xs text-gray-400">Grafik interaktif, bisa print ke PDF</div>
                </div>
              </div>
              {downloading === 'html' ? (
                <Loader2 className="w-5 h-5 text-green-400 animate-spin" />
              ) : success === 'html' ? (
                <CheckCircle className="w-5 h-5 text-green-400" />
              ) : (
                <Download className="w-5 h-5 text-green-400" />
              )}
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
              <span className="text-sm text-red-300">{error}</span>
            </div>
          )}

          {/* Tips */}
          <div className="bg-gray-700/30 rounded-lg p-3">
            <p className="text-xs text-gray-400">
              💡 <strong>Tips:</strong> Format HTML memiliki grafik interaktif yang dapat di-zoom dan di-hover. 
              Anda juga bisa print halaman HTML ke PDF melalui browser (Ctrl+P).
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-gray-700 bg-gray-800/50">
          <button
            onClick={onClose}
            className="w-full py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
};

export default ReportModal;