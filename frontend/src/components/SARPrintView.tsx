import React, { useEffect, useState } from 'react';
import { Alert, SystemTheme } from '../types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { formatINR } from '../utils/format';

interface PrintData {
  sarReport: string;
  activeAlert: Alert;
  graphImage?: string | null;
  theme?: SystemTheme;
}

export default function SARPrintView() {
  const [data, setData] = useState<PrintData | null>(null);

  useEffect(() => {
    // Read print data from localStorage
    const saved = localStorage.getItem('fage_print_sar');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setData(parsed);
      } catch (err) {
        console.error('Failed to parse print data', err);
      }
    }
    
    // Automatically trigger print when loaded
    const timer = setTimeout(() => {
      window.print();
    }, 2000); // give ReactMarkdown and Graph a moment to render

    return () => clearTimeout(timer);
  }, []);

  if (!data) {
    return <div className="p-8 text-center text-red-600 font-bold">No SAR print data found. Please close this window and try again from the Investigation Workbench.</div>;
  }

  const { sarReport, activeAlert, graphImage, theme } = data;

  return (
    <div className="bg-white min-h-screen text-black font-serif text-sm print:bg-white print:m-0 print:p-0 p-8 max-w-4xl mx-auto">
      
      {/* HEADER */}
      <div className="border-b-2 border-black pb-4 mb-6">
        <h1 className="text-2xl font-black uppercase tracking-wider m-0">FAGE</h1>
        <h2 className="text-lg font-bold text-gray-700 m-0">Fraud Analytics & Governance Engine</h2>
        
        <div className="mt-8 text-center border-y border-gray-300 py-4 mb-8">
          <h1 className="text-3xl font-black uppercase tracking-wider m-0">SUSPICIOUS ACTIVITY REPORT</h1>
          <p className="text-md font-bold text-gray-500 uppercase tracking-widest mt-1">AI-GENERATED DRAFT — NOT FILED</p>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm font-sans mb-4">
          <div><span className="font-bold uppercase">Report ID:</span> {`SAR-${Date.now().toString().slice(-6)}`}</div>
          <div><span className="font-bold uppercase">Generated Date/Time:</span> {new Date().toLocaleString()}</div>
          <div><span className="font-bold uppercase">Alert ID:</span> {activeAlert.id}</div>
          <div><span className="font-bold uppercase">Risk Score:</span> {activeAlert.riskScore}</div>
          <div><span className="font-bold uppercase">Account ID:</span> {activeAlert.accountNumber}</div>
          <div><span className="font-bold uppercase">Risk Level:</span> {activeAlert.alertSeverity}</div>
        </div>
      </div>

      {/* 1. SUBJECT / ACCOUNT INFORMATION */}
      <div className="mb-8 avoid-break">
        <h3 className="text-lg font-bold uppercase border-b border-gray-400 pb-1 mb-3">1. SUBJECT / ACCOUNT INFORMATION</h3>
        <table className="w-full text-left border-collapse border border-gray-300 font-sans text-sm">
          <tbody>
            <tr>
              <th className="border border-gray-300 p-2 bg-gray-100 w-1/3">Account ID</th>
              <td className="border border-gray-300 p-2">{activeAlert.accountNumber}</td>
            </tr>
            <tr>
              <th className="border border-gray-300 p-2 bg-gray-100">Transaction Type</th>
              <td className="border border-gray-300 p-2">{activeAlert.type}</td>
            </tr>
            <tr>
              <th className="border border-gray-300 p-2 bg-gray-100 w-1/3">Transaction Amount</th>
              <td className="border border-gray-300 p-2 font-mono font-bold text-red-700">{formatINR(activeAlert.transactionAmount)}</td>
            </tr>
            <tr>
              <th className="border border-gray-300 p-2 bg-gray-100">Receiver Account</th>
              <td className="border border-gray-300 p-2 font-mono">{activeAlert.receiverAccountId}</td>
            </tr>
            <tr>
              <th className="border border-gray-300 p-2 bg-gray-100">Date/Time</th>
              <td className="border border-gray-300 p-2">{activeAlert.dateOpened || activeAlert.timestamp}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* 2. RISK ANALYSIS */}
      <div className="mb-8 avoid-break">
        <h3 className="text-lg font-bold uppercase border-b border-gray-400 pb-1 mb-3">2. RISK ANALYSIS</h3>
        <table className="w-full text-left border-collapse border border-gray-300 font-sans text-sm">
          <thead>
            <tr>
              <th className="border border-gray-300 p-2 bg-gray-100">Indicator / Feature</th>
              <th className="border border-gray-300 p-2 bg-gray-100">Impact</th>
              <th className="border border-gray-300 p-2 bg-gray-100">Direction</th>
            </tr>
          </thead>
          <tbody>
            {activeAlert.keyRiskDrivers && activeAlert.keyRiskDrivers.length > 0 ? (
              activeAlert.keyRiskDrivers.map((driver, idx) => (
                <tr key={idx}>
                  <td className="border border-gray-300 p-2 font-mono">{driver.feature}</td>
                  <td className="border border-gray-300 p-2">{driver.importance_attribution.toFixed(4)}</td>
                  <td className="border border-gray-300 p-2">
                    {driver.direction === 'increases_risk' ? 'Increases Risk' : 'Reduces Risk'}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3} className="border border-gray-300 p-2 text-center text-gray-500 italic">No specific risk drivers available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 3. INVESTIGATION FINDINGS */}
      <div className="mb-8 avoid-break font-sans">
        <h3 className="text-lg font-bold uppercase border-b border-gray-400 pb-1 mb-3 font-serif">3. INVESTIGATION FINDINGS</h3>
        <p className="text-sm">
          <span className="font-bold">Initial Trigger:</span> {activeAlert.reason || 'Automated model detection.'}
        </p>
        <p className="text-sm mt-2">
          <span className="font-bold">Triage Decision:</span> {activeAlert.triageDecision?.triage_action || activeAlert.triage_action || 'Pending'}
        </p>
        {activeAlert.pu_probability !== undefined && (
          <p className="text-sm mt-2">
            <span className="font-bold">Positive/Unlabeled Probability:</span> {(activeAlert.pu_probability * 100).toFixed(2)}%
          </p>
        )}
      </div>

      {/* 4. EXACT EXISTING ACCOUNT GRAPH */}
      <div className="mb-8 avoid-break font-sans">
        <h3 className="text-lg font-bold uppercase border-b border-gray-400 pb-1 mb-3 font-serif">4. INVESTIGATION RELATIONSHIP GRAPH</h3>
        <p className="text-sm mb-2">
          <span className="font-bold">Account:</span> {activeAlert.accountNumber} <br />
          <span className="font-bold">Alert:</span> {activeAlert.id}
        </p>
        <div 
          className="border border-gray-300 w-full mb-2 flex items-center justify-center overflow-hidden" 
          style={{ backgroundColor: theme === 'sovereign' ? '#f8fafc' : '#0a0f11' }}
        >
          {graphImage ? (
            <img src={graphImage} alt="Investigation Relationship Graph" className="max-w-full max-h-[500px] object-contain" />
          ) : (
            <div className="p-8 text-gray-500 italic">Graph image not captured.</div>
          )}
        </div>
        <div className="p-2.5 rounded border text-xs flex flex-col gap-1 font-sans bg-amber-50 border-amber-300 text-amber-800">
          <div className="font-bold uppercase tracking-wider flex items-center gap-1">
            ⚠️ INVESTIGATION SIMULATION
          </div>
          <div>
            The underlying dataset does not provide verified relational identifiers. Relationships shown in this graph are mathematically synthesized for investigation demonstration purposes and must not be interpreted as verified transaction relationships.
          </div>
        </div>
      </div>

      {/* 5. SAR NARRATIVE */}
      <div className="mb-8">
        <h3 className="text-lg font-bold uppercase border-b border-gray-400 pb-1 mb-3">5. SAR NARRATIVE</h3>
        <div className="sar-markdown-content break-words leading-relaxed font-sans text-sm border-l-4 border-gray-800 pl-4 py-2 bg-gray-50">
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({node, ...props}) => <h1 className="text-lg font-bold uppercase mt-4 mb-2" {...props} />,
              h2: ({node, ...props}) => <h2 className="text-md font-bold uppercase mt-4 mb-2" {...props} />,
              h3: ({node, ...props}) => <h3 className="text-sm font-bold mt-3 mb-1" {...props} />,
              p: ({node, ...props}) => <p className="mb-3" {...props} />,
              ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-3" {...props} />,
              ol: ({node, ...props}) => <ol className="list-decimal pl-5 mb-3" {...props} />,
              li: ({node, ...props}) => <li className="mb-1" {...props} />,
              table: ({node, ...props}) => <table className="w-full border-collapse border border-gray-300 mb-4" {...props} />,
              th: ({node, ...props}) => <th className="border border-gray-300 bg-gray-100 p-2 text-left font-bold" {...props} />,
              td: ({node, ...props}) => <td className="border border-gray-300 p-2" {...props} />,
              blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-gray-300 bg-gray-100 py-2 px-4 mb-3 italic" {...props} />,
              strong: ({node, ...props}) => <strong className="font-bold" {...props} />,
            }}
          >
            {sarReport}
          </ReactMarkdown>
        </div>
      </div>

      {/* 6. MODEL INFORMATION */}
      <div className="mb-8 avoid-break font-sans">
        <h3 className="text-lg font-bold uppercase border-b border-gray-400 pb-1 mb-3 font-serif">6. MODEL INFORMATION</h3>
        <div className="grid grid-cols-3 gap-4 text-sm bg-gray-100 p-4 border border-gray-300">
          <div>
            <span className="block font-bold uppercase text-gray-600">Model</span>
            <span>XGBoost</span>
          </div>
          <div>
            <span className="block font-bold uppercase text-gray-600">Features</span>
            <span>353</span>
          </div>
          <div>
            <span className="block font-bold uppercase text-gray-600">Decision Threshold</span>
            <span>0.60</span>
          </div>
        </div>
      </div>

      {/* 7. AI-GENERATED CONTENT DISCLAIMER */}
      <div className="mb-8 avoid-break font-sans bg-amber-50 border border-amber-300 p-4">
        <h3 className="text-md font-bold uppercase text-amber-800 mb-2">7. AI-GENERATED CONTENT DISCLAIMER</h3>
        <p className="text-sm font-bold text-amber-900 mb-1 uppercase tracking-wider">AI-generated draft — Human review required.</p>
        <p className="text-sm text-amber-900">
          This report has not been independently verified and must be reviewed against the underlying transaction and investigation evidence before any regulatory filing.
        </p>
      </div>

      {/* 8. FILING STATUS */}
      <div className="mb-8 avoid-break font-sans border-t-2 border-black pt-4">
        <h3 className="text-lg font-bold uppercase mb-2 font-serif">8. FILING STATUS</h3>
        <div className="inline-block border-4 border-red-600 text-red-600 px-6 py-2 text-xl font-black uppercase tracking-widest transform -rotate-3">
          NOT FILED
        </div>
      </div>
      
    </div>
  );
}
