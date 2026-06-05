import React, { useState } from 'react';
import { 
  FolderOpen, 
  Copy, 
  Check, 
  X, 
  ShieldAlert, 
  BarChart, 
  Users, 
  Layers, 
  Pocket, 
  Edit3, 
  Send,
  Workflow,
  Download
} from 'lucide-react';
import { Alert, SHAPDriver, AnalystNote, SystemTheme } from '../types';

interface InvestigationWorkbenchViewProps {
  activeAlert: Alert;
  drivers: SHAPDriver[];
  notes: Record<string, AnalystNote[]>;
  onAddNote: (id: string, noteText: string) => void;
  onUpdateStatus: (id: string, status: 'Open' | 'Escalated' | 'Closed' | 'Investigating') => void;
  onUpdateAssignment?: (id: string, assignee: string) => void;
  theme: SystemTheme;
  alerts?: Alert[];
  onSelectAlert?: (id: string) => void;
}

export default function InvestigationWorkbenchView({
  activeAlert,
  drivers,
  notes,
  onAddNote,
  onUpdateStatus,
  onUpdateAssignment,
  theme,
  alerts,
  onSelectAlert
}: InvestigationWorkbenchViewProps) {
  const isDark = theme === 'sovereign';
  const [copied, setCopied] = useState(false);
  const [noteContent, setNoteContent] = useState('');
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [activeNoteTab, setActiveNoteTab] = useState<'notes' | 'logs'>('notes');

  const formatUSD = (val: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(val);
  };

  const getPredictionDescription = () => {
    if (activeAlert.reason) {
      return activeAlert.reason;
    }
    if (activeAlert.riskScore >= 75) {
      return "Pattern matching algorithm confirms synchronized token routing, layered external transfers, and rapid outflow velocity.";
    } else if (activeAlert.riskScore >= 50) {
      return "ML anomaly flags elevated transfer frequencies and minor deviation profiles. Recommend manual verification of beneficiary details.";
    } else {
      return "Model confirms behavioral patterns reside fully within normal operational baselines. No anomalous velocity signatures detected.";
    }
  };

  const getPredictionIndicator = () => {
    if (activeAlert.riskScore >= 75) {
      return (
        <div className="flex items-center gap-2 text-xs font-bold text-red-500 mt-4">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
          <span>Action Required</span>
        </div>
      );
    } else if (activeAlert.riskScore >= 50) {
      return (
        <div className="flex items-center gap-2 text-xs font-bold text-amber-500 mt-4">
          <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
          <span>Review Recommended</span>
        </div>
      );
    } else {
      return (
        <div className="flex items-center gap-2 text-xs font-bold text-emerald-500 mt-4">
          <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
          <span>Clear / Low Risk</span>
        </div>
      );
    }
  };

  const getConfidenceDescription = () => {
    const val = activeAlert.confidenceVal || 50;
    if (val >= 85) {
      return "High decile consensus across multiple system-level ensemble modeling predictors.";
    } else if (val >= 60) {
      return "Moderate consensus between neural network classifiers and tree-based decision ensembles.";
    } else {
      return "Marginal decision consensus. Heuristic overrides and ML boundaries are within close variance.";
    }
  };

  // Connection Nodes for Resolved Entity Graph representation helper functions
  const getDynamicIP = (seed: string) => {
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
      hash = seed.charCodeAt(i) + ((hash << 5) - hash);
    }
    const octet3 = Math.abs((hash >> 8) % 254) + 1;
    const octet4 = Math.abs(hash % 254) + 1;
    return `Proxy IP: 45.19.${octet3}.${octet4}`;
  };

  const getDynamicDevice = (seed: string) => {
    const devices = [
      'AppleMac_F12', 'WinDesktop_X85', 'iPhone_15Pro', 
      'Samsung_S24', 'LinuxClient_U91', 'ChromeBook_E11',
      'iPadPro_M2', 'OnePlus_12', 'Pixel_8Pro'
    ];
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
      hash = seed.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % devices.length;
    return `Device: ${devices[index]}`;
  };

  const graphNodes = [
    { id: '1', label: 'Primary Mule Acct', role: 'Target', x: 150, y: 100, color: '#ef4444' },
    { id: '2', label: getDynamicIP(activeAlert.id), role: 'Network', x: 50, y: 50, color: '#3b82f6' },
    { id: '3', label: getDynamicDevice(activeAlert.id), role: 'Fingerprint', x: 250, y: 40, color: '#06b6d4' },
    { id: '4', label: 'Co-applicant Layer Profile', role: 'ID Synthetic', x: 260, y: 150, color: '#f59e0b' },
    { id: '5', label: 'External Sink Routing', role: 'Transit', x: 70, y: 160, color: '#a855f7' }
  ];

  // Connection routes
  const graphLinks = [
    { source: '1', target: '2' },
    { source: '1', target: '3' },
    { source: '1', target: '4' },
    { source: '1', target: '5' },
    { source: '3', target: '4' }
  ];

  const handleCopy = () => {
    navigator.clipboard.writeText(activeAlert.accountNumber);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSaveNote = () => {
    if (!noteContent.trim()) return;
    onAddNote(activeAlert.id, noteContent.trim());
    setNoteContent('');
  };

  const handleExportJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({
      caseDetails: activeAlert,
      drivers: drivers,
      notes: caseNotes
    }, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `fage-case-report-${activeAlert.id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const caseNotes = React.useMemo(() => {
    const list = [...(notes[activeAlert.id] || [])];
    
    if (activeAlert.logs) {
      activeAlert.logs.forEach((log, idx) => {
        if (log.action.startsWith('Appended Analyst Note: ')) {
          const noteText = log.action.replace('Appended Analyst Note: ', '');
          if (!list.some(n => n.content === noteText)) {
            list.push({
              id: `api-note-${activeAlert.id}-${idx}`,
              author: log.operator,
              timestamp: log.timestamp,
              content: noteText,
              isSystem: log.operator.toLowerCase().includes('system')
            });
          }
        }
      });
    }
    return list;
  }, [notes, activeAlert]);

  return (
    <div className="space-y-6">
      {/* Workbench Header Section */}
      <div className={`flex flex-col md:flex-row md:items-center justify-between p-4 border-b rounded-xl ${
        isDark ? 'bg-slate-900/40 border-slate-800' : 'bg-white border-[#c4c5d5] shadow-sm'
      }`}>
        <div>
          <div className="flex flex-wrap items-center gap-3 text-xs font-semibold text-slate-400 mb-2">
            <FolderOpen size={13} className="shrink-0" />
            <span className="uppercase tracking-widest font-mono shrink-0">Select Case:</span>
            {alerts && onSelectAlert && (
              <select
                value={activeAlert.id}
                onChange={(e) => onSelectAlert(e.target.value)}
                className={`font-sans text-xs px-2 py-0.5 rounded outline-none border cursor-pointer ${
                  isDark 
                    ? 'bg-slate-900 border-slate-700 text-slate-350 focus:border-cyan-500' 
                    : 'bg-white border-[#c4c5d5] text-slate-650'
                }`}
              >
                {alerts.map(a => (
                  <option key={a.id} value={a.id}>
                    {a.id} ({a.accountNumber.replace('ACC-TGT-', 'TGT-')}) - {a.riskScore}/100
                  </option>
                ))}
              </select>
            )}
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
              activeAlert.status === 'Escalated' 
                ? 'bg-red-950/40 text-red-300 border border-red-500/10' 
                : 'bg-amber-100 text-amber-800 dark:bg-amber-950/20 dark:text-amber-300'
            }`}>
              {activeAlert.status === 'Escalated' ? 'Escalated Priority' : 'High Priority'}
            </span>
          </div>

          <h2 className={`text-xl font-black flex items-center gap-2 ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
            <span>Acct: {activeAlert.accountNumber}</span>
            <button 
              onClick={handleCopy}
              className="p-1 rounded text-slate-400 hover:text-slate-200 transition-colors"
              title="Copy Account Code"
            >
              {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={13} />}
            </button>
          </h2>
        </div>

        {/* Action Triggers */}
        <div className="flex items-center gap-3 mt-3 md:mt-0 font-sans">
          <button 
            onClick={handleExportJSON}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-300 border ${
              isDark 
                ? 'border-slate-800 text-slate-300 hover:bg-slate-800 bg-slate-900/40 hover:text-white' 
                : 'border-[#c4c5d5] text-slate-700 hover:bg-slate-100 bg-white shadow-sm hover:text-slate-900'
            }`}
            title="Export Case Details and Audit Timeline as JSON"
          >
            <Download size={14} />
            <span>Export Case</span>
          </button>

          <button 
            onClick={() => onUpdateStatus(activeAlert.id, 'Closed')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-colors border ${
              activeAlert.status === 'Closed'
                ? 'bg-emerald-950/30 text-emerald-300 border-emerald-500'
                : (isDark 
                  ? 'border-slate-800 text-slate-300 hover:bg-slate-800 bg-slate-900/40' 
                  : 'border-[#c4c5d5] text-slate-700 hover:bg-slate-100 bg-white shadow-sm'
                )
            }`}
          >
            <X size={14} />
            <span>Close Case</span>
          </button>
          
          <button 
            onClick={() => onUpdateStatus(activeAlert.id, 'Escalated')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-colors ${
              activeAlert.status === 'Escalated'
                ? 'bg-red-600 hover:bg-red-700 text-white shadow-sm'
                : (isDark 
                  ? 'bg-cyan-500 hover:bg-cyan-600 text-[#051424] cyan-glow' 
                  : 'bg-[#1e40af] hover:bg-opacity-95 text-white'
                )
            }`}
          >
            <ShieldAlert size={14} className="animate-pulse" />
            <span>Escalate Case</span>
          </button>
        </div>
      </div>

      {/* Grid Canvas Section (3:1 bento division) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Span - Risk & Features (2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Top KPI Bento Block */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Score Ring Meter card */}
            <div className={`p-4 border rounded-xl flex flex-col justify-center items-center min-h-[12rem] h-auto ${
              isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
            }`}>
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-3 block">Model Risk Score</span>
              <div className="relative w-28 h-28 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90">
                  <circle cx="56" cy="56" r="44" fill="transparent" stroke={isDark ? '#1e293b' : '#eeedf7'} strokeWidth="8"/>
                  <circle 
                    cx="56" cy="56" r="44" 
                    fill="transparent" 
                    stroke="#ef4444" 
                    strokeWidth="8"
                    strokeDasharray={2 * Math.PI * 44}
                    strokeDashoffset={(1 - (activeAlert.riskScore / 100)) * (2 * Math.PI * 44)}
                    strokeLinecap="round"
                    className="transition-all duration-1000"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span className="text-3xl font-extrabold tracking-tight text-red-500">{activeAlert.riskScore}</span>
                  <span className="text-[9px] text-slate-400 tracking-wider">/ 100 max</span>
                </div>
              </div>
            </div>

            {/* Prediction details */}
            <div className={`p-4 border rounded-xl flex flex-col justify-between min-h-[12rem] h-auto ${
              isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
            }`}>
              <div>
                <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-2 block">Prediction Status</span>
                <h3 className={`text-md font-bold leading-tight ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
                  {activeAlert.type}
                </h3>
                <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                  {getPredictionDescription()}
                </p>
              </div>

              {getPredictionIndicator()}
            </div>

            {/* Confidence detail bar */}
            <div className={`p-4 border rounded-xl flex flex-col justify-between min-h-[12rem] h-auto ${
              isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
            }`}>
              <div>
                <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-2 block">Confidence Level</span>
                <div className="flex items-baseline gap-1 mt-1">
                  <span className={`text-3xl font-extrabold ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
                    {activeAlert.confidenceVal}%
                  </span>
                </div>
                <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden mt-3">
                  <div className={`h-full rounded-full ${isDark ? 'bg-cyan-400' : 'bg-[#1e40af]'}`} style={{ width: `${activeAlert.confidenceVal}%` }}></div>
                </div>
              </div>

              <p className="text-[11px] text-slate-400 leading-normal mt-4">
                {getConfidenceDescription()}
              </p>
            </div>
          </div>

          {/* Top SHAP Drivers relative layout */}
          <div className={`p-5 border rounded-xl ${
            isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
          }`}>
            <div className="flex justify-between items-center mb-5 border-b border-slate-300 dark:border-slate-800 pb-2">
              <h3 className={`text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                Top Risk Drivers (SHAP Values)
              </h3>
              <span className="text-[10px] text-indigo-500 font-semibold cursor-pointer hover:underline">Base offset: +0.15</span>
            </div>

            <div className="space-y-4">
              {drivers.slice(0, 4).map((d) => {
                const isPositive = d.shapValue > 0;
                const valuePercent = Math.min(Math.abs(d.shapValue) * 100, 100);
                
                return (
                  <div key={d.featureId} className="space-y-1">
                    <div className="flex justify-between text-xs font-bold leading-none">
                      <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>{d.name}</span>
                      <span className={isPositive ? 'text-red-500' : 'text-emerald-500'}>
                        {isPositive ? '+' : ''}{d.shapValue.toFixed(2)}
                      </span>
                    </div>

                    <div className="h-4 flex items-center relative">
                      {/* Aligned zero marker vertical line at 30% width */}
                      <div className="absolute left-[30%] top-0 bottom-0 w-px bg-slate-300 dark:bg-slate-800 z-10"></div>
                      <div className="w-full bg-slate-100 dark:bg-slate-900/40 rounded-full h-2 overflow-hidden flex relative">
                        {isPositive ? (
                          <>
                            <div className="h-full" style={{ width: '30%' }}></div>
                            <div className="bg-red-500 h-full rounded-r" style={{ width: `${valuePercent}%` }}></div>
                          </>
                        ) : (
                          <>
                            <div className="h-full" style={{ width: `${30 - valuePercent}%` }}></div>
                            <div className="bg-emerald-500 h-full rounded-l" style={{ width: `${valuePercent}%` }}></div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Interactive Entity Resolution Network vector graph canvas */}
          <div className={`p-5 border rounded-xl relative ${
            isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
          }`}>
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className={`text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                  Entity Resolution Network
                </h3>
                <span className="text-[10px] text-slate-400 block mt-0.5">Identified synthetic proxies matching risk markers</span>
              </div>
              <Workflow size={16} className="text-slate-400" />
            </div>

            {/* Resolved interactive SVG Canvas mapping */}
            <div className="h-64 border border-dashed border-slate-300 dark:border-slate-800 rounded-lg relative overflow-hidden bg-slate-950/20 flex items-center justify-center">
              <svg className="w-full h-full" viewBox="0 0 320 200" preserveAspectRatio="xMidYMid meet">
                {/* Back-links routing */}
                {graphLinks.map((link, i) => {
                  const sNode = graphNodes.find(n => n.id === link.source)!;
                  const tNode = graphNodes.find(n => n.id === link.target)!;
                  return (
                    <line 
                      key={i}
                      x1={sNode.x} y1={sNode.y}
                      x2={tNode.x} y2={tNode.y}
                      stroke={isDark ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.1)'}
                      strokeWidth="2"
                    />
                  );
                })}

                {/* Nodes rendering */}
                {graphNodes.map((node) => (
                  <g 
                    key={node.id}
                    className="cursor-pointer group"
                    onMouseEnter={() => setHoveredNode(node.label)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    <circle 
                      cx={node.x} cy={node.y}
                      r="12"
                      fill={node.color}
                      className="transition-all duration-300 hover:scale-130 origin-center"
                    />
                    <circle 
                      cx={node.x} cy={node.y}
                      r="18"
                      fill="transparent"
                      stroke={node.color}
                      strokeWidth="1.5"
                      className="animate-pulse opacity-40"
                    />
                  </g>
                ))}
              </svg>

              {/* Dynamic node tooltip helper */}
              <div className="absolute top-2 left-2 flex items-center bg-[#0d1c2d] text-cyan-200 text-[10px] font-mono px-2 py-0.5 rounded border border-cyan-500/10">
                <span>GRAPH MODE: D3 / WEBGL ACTIVE</span>
              </div>

              {hoveredNode && (
                <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-slate-950 text-white text-xs px-3 py-1 rounded shadow-lg border border-slate-800">
                  {hoveredNode}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Section Details, notes (1 col) */}
        <div className="space-y-6">
          {/* Account detail list block */}
          <div className={`p-4 border rounded-xl ${
            isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
          }`}>
            <h3 className={`text-xs font-bold uppercase tracking-wider mb-4 border-b border-slate-300 dark:border-slate-800 pb-2 ${
              isDark ? 'text-slate-200' : 'text-slate-700'
            }`}>
              Account Details
            </h3>

            <dl className="space-y-3.5 text-xs">
              <div className="flex justify-between border-b border-slate-300/20 dark:border-slate-800/20 pb-1.5">
                <dt className="text-slate-400">Holder Name</dt>
                <dd className="font-bold text-right">{activeAlert.holderName}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-300/20 dark:border-slate-800/20 pb-1.5">
                <dt className="text-slate-400">SSN (Last 4)</dt>
                <dd className="font-mono text-right font-semibold">{activeAlert.ssn}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-300/20 dark:border-slate-800/20 pb-1.5">
                <dt className="text-slate-400">Date Opened</dt>
                <dd className="font-semibold text-right">{activeAlert.dateOpened}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-300/20 dark:border-slate-800/20 pb-1.5 items-center">
                <dt className="text-slate-400">Assigned To</dt>
                <dd className="font-bold text-right">
                  {onUpdateAssignment ? (
                    <select
                      value={activeAlert.assignedTo || 'Unassigned'}
                      onChange={(e) => onUpdateAssignment(activeAlert.id, e.target.value)}
                      className={`font-sans text-[11px] px-2 py-0.5 rounded outline-none border cursor-pointer ${
                        isDark 
                          ? 'bg-slate-900 border-slate-700 text-slate-350 focus:border-cyan-500' 
                          : 'bg-white border-[#c4c5d5] text-slate-650'
                      }`}
                    >
                      <option value="Unassigned">Unassigned</option>
                      <option value="Admin (Operator)">Admin (Operator)</option>
                      <option value="V. Vance (Analyst)">V. Vance (Analyst)</option>
                      <option value="J. Doe (Analyst)">J. Doe (Analyst)</option>
                    </select>
                  ) : (
                    <span>{activeAlert.assignedTo || 'Unassigned'}</span>
                  )}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-300/20 dark:border-slate-800/20 pb-1.5">
                <dt className="text-slate-400">Current Balance</dt>
                <dd className="font-semibold text-right text-indigo-500">{formatUSD(activeAlert.balance)}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-300/20 dark:border-slate-800/20 pb-1.5">
                <dt className="text-slate-400">YTD Inflows</dt>
                <dd className="font-bold text-right text-emerald-500">{formatUSD(activeAlert.ytdInflows)}</dd>
              </div>
              <div className="flex justify-between pb-1.5">
                <dt className="text-slate-400">YTD Outflows</dt>
                <dd className="font-bold text-right text-[#ba1a1a]">{formatUSD(activeAlert.ytdOutflows)}</dd>
              </div>
            </dl>
          </div>

          {/* Case investigation notes list timeline with tabbed System Audit Logs view */}
          <div className={`p-4 border rounded-xl flex flex-col min-h-[340px] ${
            isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
          }`}>
            {/* Custom Notes/Logs Tabs Selector */}
            <div className="flex border-b border-slate-300 dark:border-slate-800 mb-4 pb-px text-[11px] font-sans">
              <button 
                onClick={() => setActiveNoteTab('notes')}
                className={`pb-2 px-1 font-bold uppercase tracking-wider transition-colors mr-4 border-b-2 ${
                  activeNoteTab === 'notes'
                    ? (isDark ? 'border-cyan-450 text-cyan-400' : 'border-[#1e40af] text-[#1e40af]')
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                Analyst Notes
              </button>
              <button 
                onClick={() => setActiveNoteTab('logs')}
                className={`pb-2 px-1 font-bold uppercase tracking-wider transition-colors border-b-2 ${
                  activeNoteTab === 'logs'
                    ? (isDark ? 'border-cyan-450 text-cyan-400' : 'border-[#1e40af] text-[#1e40af]')
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                System Audit Logs
              </button>
            </div>

            {/* Note records iterator list */}
            {activeNoteTab === 'notes' ? (
              <div className="flex-1 space-y-3.5 overflow-y-auto max-h-56 pr-2 mb-4 scrollbar-thin">
                {caseNotes.length > 0 ? (
                  caseNotes.map((note) => (
                    <div 
                      key={note.id}
                      className={`p-2.5 rounded-lg border text-xs leading-relaxed ${
                        note.isSystem 
                          ? 'bg-red-950/20 border-red-500/20 text-slate-300' 
                          : (isDark 
                            ? 'bg-slate-800/50 border-slate-700 text-slate-300' 
                            : 'bg-[#f4f2fc] border-[#c4c5d5] text-slate-700'
                          )
                      }`}
                    >
                      <div className="flex justify-between items-center text-[10px] font-bold text-slate-400 mb-1 leading-none">
                        <span>{note.author}</span>
                        <span>{note.timestamp}</span>
                      </div>
                      <p>{note.content}</p>
                    </div>
                  ))
                ) : (
                  <div className="text-center p-8 text-slate-400 text-xs">No analyst notes added to this case yet.</div>
                )}
              </div>
            ) : (
              <div className="flex-1 space-y-3 overflow-y-auto max-h-56 pr-2 mb-4 scrollbar-thin font-mono text-[10px]">
                {activeAlert.logs && activeAlert.logs.length > 0 ? (
                  activeAlert.logs.map((log, idx) => (
                    <div 
                      key={idx}
                      className={`p-2 rounded border border-dashed border-slate-300/40 dark:border-slate-800/60 leading-normal ${
                        isDark ? 'bg-slate-900/20' : 'bg-slate-50'
                      }`}
                    >
                      <div className="flex justify-between text-[9px] font-bold text-slate-500 mb-0.5 leading-none">
                        <span>{log.operator}</span>
                        <span>{log.timestamp}</span>
                      </div>
                      <div className={isDark ? 'text-slate-300' : 'text-slate-700'}>{log.action}</div>
                    </div>
                  ))
                ) : (
                  <div className="text-center p-8 text-slate-400">No system audit logs found for this case.</div>
                )}
              </div>
            )}

            {/* Add note input area (only available on Notes tab) */}
            {activeNoteTab === 'notes' && (
              <div className="mt-auto space-y-2 pt-2 border-t border-slate-300 dark:border-slate-800">
                <textarea 
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  placeholder="Enter investigation notes/rationale for case escalation..."
                  className={`w-full text-xs font-sans p-2 rounded-lg border focus:ring-1 focus:outline-none resize-none ${
                    isDark 
                      ? 'bg-slate-950 border-slate-700 text-slate-300 focus:border-cyan-500 focus:ring-cyan-500' 
                      : 'bg-white border-[#c4c5d5] text-slate-700 focus:border-[#1e40af] focus:ring-[#1e40af]'
                  }`}
                  rows={4}
                />
                <div className="flex items-center justify-between leading-none">
                  <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">Internal access list only</span>
                  <button
                    onClick={handleSaveNote}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-bold transition-all duration-300 ${
                      isDark 
                        ? 'bg-cyan-500 hover:bg-cyan-600 text-[#051424]' 
                        : 'bg-[#1e40af] hover:bg-opacity-95 text-white'
                    }`}
                  >
                    <Send size={11} />
                    <span>Save Note</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
