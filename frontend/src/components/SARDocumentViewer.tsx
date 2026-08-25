import React, { useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  Printer, 
  Copy, 
  RefreshCw, 
  X, 
  AlertTriangle,
  FileText,
  CheckCircle2
} from 'lucide-react';

import { Alert, SystemTheme } from '../types';

interface SARDocumentViewerProps {
  sarReport: string;
  activeAlert: Alert;
  getGraphImage: () => string | null;
  theme: SystemTheme;
  onRegenerate: () => void;
  isGenerating: boolean;
  onClose: () => void;
}

export default function SARDocumentViewer({
  sarReport,
  activeAlert,
  getGraphImage,
  theme,
  onRegenerate,
  isGenerating,
  onClose
}: SARDocumentViewerProps) {
  const [copied, setCopied] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const handleCopy = async () => {
    if (!contentRef.current) return;
    try {
      const text = contentRef.current.innerText;
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy SAR text:', err);
    }
  };

  const handlePrint = () => {
    const graphImage = getGraphImage();
    localStorage.setItem('fage_print_sar', JSON.stringify({
      sarReport,
      activeAlert,
      graphImage,
      theme
    }));
    window.open(`/sar-report/${activeAlert.id}`, '_blank');
  };

  return (
    <div className="sar-document-container flex flex-col bg-surface border border-outline-variant rounded-xl shadow-lg overflow-hidden h-full max-h-[800px]">
      {/* ACTION BAR */}
      <div className="flex items-center justify-between p-3 border-b border-outline-variant bg-surface-container-lowest print:hidden">
        <div className="flex items-center gap-2 text-primary font-bold text-sm">
          <FileText size={18} />
          <span>SAR Review Workspace</span>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-surface-container hover:bg-surface-container-high text-on-surface rounded transition-colors"
          >
            {copied ? <CheckCircle2 size={14} className="text-emerald-500" /> : <Copy size={14} />}
            {copied ? 'Copied' : 'Copy Report'}
          </button>
          <button 
            onClick={handlePrint}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-surface-container hover:bg-surface-container-high text-on-surface rounded transition-colors"
          >
            <Printer size={14} />
            Download/Print
          </button>
          <button 
            onClick={onRegenerate}
            disabled={isGenerating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-primary/10 hover:bg-primary/20 text-primary rounded transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={isGenerating ? 'animate-spin' : ''} />
            {isGenerating ? 'Generating...' : 'Regenerate'}
          </button>
          <div className="w-px h-4 bg-outline-variant mx-1"></div>
          <button 
            onClick={onClose}
            className="p-1.5 text-on-surface-variant hover:bg-error/10 hover:text-error rounded transition-colors"
            title="Close Viewer"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* DOCUMENT SCROLL AREA */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-6 md:p-8 bg-[#fafafa] print:p-0 print:bg-white text-black">
        
        {/* DOCUMENT HEADER / METADATA */}
        <div className="max-w-4xl mx-auto bg-white border border-gray-200 p-8 md:p-12 shadow-sm rounded-sm print:border-none print:shadow-none print:p-0">
          
          {/* Status Badge & Label */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b-2 border-black pb-4 mb-6">
            <div>
              <h1 className="text-2xl font-black uppercase tracking-wider m-0">AI-GENERATED SAR DRAFT</h1>
              <p className="text-sm font-bold text-gray-500 uppercase tracking-widest mt-1">AI-generated — Human Review Required</p>
            </div>
            <div className="mt-4 sm:mt-0 px-3 py-1 border-2 border-red-600 text-red-600 font-bold text-sm uppercase tracking-wider transform -rotate-2">
              NOT YET FILED
            </div>
          </div>

          {/* Review Warning Block */}
          <div className="bg-amber-50 border-l-4 border-amber-500 p-4 mb-8 text-sm text-amber-900 print:border-l-4 print:border-gray-800 print:text-black">
            <h4 className="font-bold uppercase tracking-wider flex items-center gap-2 mb-2 text-amber-700 print:text-black">
              <AlertTriangle size={16} />
              AI-GENERATED DRAFT — HUMAN REVIEW REQUIRED
            </h4>
            <p className="m-0 leading-relaxed">
              This narrative has been generated by an AI system and has not been independently verified. A qualified reviewer must validate the information against the underlying transaction and investigation evidence before any regulatory filing. For analyst/compliance review only.
            </p>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 text-sm bg-gray-50 p-4 border border-gray-200 print:bg-white print:border-gray-300">
            <div>
              <span className="block text-xs font-bold text-gray-500 uppercase">Report ID</span>
              <span className="font-mono font-medium">{`SAR-${Date.now().toString().slice(-6)}`}</span>
            </div>
            <div>
              <span className="block text-xs font-bold text-gray-500 uppercase">Alert ID</span>
              <span className="font-mono font-medium">{activeAlert.id}</span>
            </div>
            <div>
              <span className="block text-xs font-bold text-gray-500 uppercase">Account ID</span>
              <span className="font-mono font-medium">{activeAlert.accountNumber}</span>
            </div>
            <div>
              <span className="block text-xs font-bold text-gray-500 uppercase">Generated At</span>
              <span className="font-medium">{new Date().toLocaleString()}</span>
            </div>
            <div>
              <span className="block text-xs font-bold text-gray-500 uppercase">Risk Score</span>
              <span className="font-medium font-mono text-red-600">{activeAlert.riskScore}</span>
            </div>
            <div>
              <span className="block text-xs font-bold text-gray-500 uppercase">Risk Level</span>
              <span className="font-medium uppercase">{activeAlert.alertSeverity}</span>
            </div>
            <div>
              <span className="block text-xs font-bold text-gray-500 uppercase">Model</span>
              <span className="font-medium">XGBoost D-0.60</span>
            </div>
            <div>
              <span className="block text-xs font-bold text-gray-500 uppercase">Report Status</span>
              <span className="font-medium font-bold text-amber-600 uppercase">Draft — Not Filed</span>
            </div>
          </div>

          <div 
            ref={contentRef}
            className="sar-markdown-content break-words text-sm leading-relaxed"
          >
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({node, ...props}) => <h1 className="text-xl font-bold uppercase border-b-2 border-gray-200 pb-2 mb-4 mt-6 text-black" {...props} />,
                h2: ({node, ...props}) => <h2 className="text-lg font-bold uppercase mt-8 mb-4 text-black" {...props} />,
                h3: ({node, ...props}) => <h3 className="text-md font-bold mt-6 mb-3 text-black" {...props} />,
                p: ({node, ...props}) => <p className="mb-4 text-gray-800" {...props} />,
                ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-4 text-gray-800 space-y-1" {...props} />,
                ol: ({node, ...props}) => <ol className="list-decimal pl-5 mb-4 text-gray-800 space-y-1" {...props} />,
                li: ({node, ...props}) => <li className="mb-1" {...props} />,
                a: ({node, ...props}) => <a className="text-blue-600 hover:underline" {...props} />,
                table: ({node, ...props}) => <div className="overflow-x-auto mb-6"><table className="min-w-full border-collapse border border-gray-300" {...props} /></div>,
                th: ({node, ...props}) => <th className="border border-gray-300 bg-gray-100 p-2 text-left font-bold text-black" {...props} />,
                td: ({node, ...props}) => <td className="border border-gray-300 p-2 text-gray-800" {...props} />,
                blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-gray-300 bg-gray-50 py-2 px-4 mb-4 text-gray-700 italic" {...props} />,
                strong: ({node, ...props}) => <strong className="font-bold text-black" {...props} />,
              }}
            >
              {sarReport}
            </ReactMarkdown>
          </div>
          
        </div>
      </div>
    </div>
  );
}
