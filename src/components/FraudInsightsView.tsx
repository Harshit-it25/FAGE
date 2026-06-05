import React, { useState, useMemo } from 'react';
import { 
  Search, 
  Download, 
  HelpCircle, 
  TrendingUp, 
  Filter, 
  Flame, 
  Group, 
  Target, 
  ShieldCheck,
  Sparkles,
  Award
} from 'lucide-react';
import { FraudCluster, OutlierEvent, SystemTheme, Alert } from '../types';
import { fraudClusters, outlierEvents } from '../data';

interface FraudInsightsViewProps {
  alerts: Alert[];
  onSelectAlert: (id: string) => void;
  theme: SystemTheme;
}

export default function FraudInsightsView({ alerts, onSelectAlert, theme }: FraudInsightsViewProps) {
  const isDark = theme === 'sovereign';
  const [hoveredPoint, setHoveredPoint] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [limitClusters, setLimitClusters] = useState(true);

  // Filter clusters based on search query and limit toggle
  const filteredClusters = useMemo(() => {
    const result = fraudClusters.filter(fc => 
      fc.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      fc.description.toLowerCase().includes(searchQuery.toLowerCase())
    );
    return limitClusters ? result.slice(0, 3) : result;
  }, [searchQuery, limitClusters]);

  // Filter outlier events (targets) based on search query
  const filteredOutliers = useMemo(() => {
    const outliers = alerts.filter(a => a.riskScore >= 50);
    return outliers.filter(a => 
      a.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.accountNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.holderName.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [alerts, searchQuery]);

  const handleExportOutliers = () => {
    const headers = ['Event ID', 'Detection Time', 'Account Target', 'Risk Score'];
    const rows = filteredOutliers.map(a => [
      a.id,
      a.timestamp,
      a.accountNumber,
      a.riskScore
    ]);
    const csvContent = "data:text/csv;charset=utf-8," 
      + [headers.join(','), ...rows.map(row => row.map(val => `"${val}"`).join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `FAGE_Outlier_Events_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Anomaly scatter coordinates
  const normalPoints = [
    { x: 50, y: 160, label: 'Normal #101' },
    { x: 80, y: 140, label: 'Normal #102' },
    { x: 100, y: 135, label: 'Normal #103' },
    { x: 120, y: 120, label: 'Normal #104' },
    { x: 150, y: 110, label: 'Normal #105' },
    { x: 180, y: 100, label: 'Normal #106' },
    { x: 210, y: 92, label: 'Normal #107' },
    { x: 230, y: 95, label: 'Normal #108' },
    { x: 260, y: 115, label: 'Normal #109' },
    { x: 280, y: 130, label: 'Normal #110' },
  ];

  const outlierPoints = useMemo(() => {
    return alerts
      .filter(a => a.riskScore >= 50)
      .map((a) => {
        // Map balance/amount to X axis coordinate (0 to 300)
        // Standard range is up to $200k
        const x = Math.min((a.balance / 200000) * 280 + 20, 290);
        
        // Map risk score to Y axis coordinate (0 is top, 220 is bottom)
        // Risk scores are 0 to 100.
        const y = 220 - (a.riskScore / 100) * 180;
        
        return {
          x,
          y,
          accountNo: a.accountNumber,
          label: `Acct: ${a.accountNumber} | Score: ${a.riskScore}/100 | Bal: $${a.balance.toLocaleString()}`
        };
      });
  }, [alerts]);

  const getClusterSeverityChip = (sev: string) => {
    switch (sev) {
      case 'Critical':
        return (
          <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-[#ffdad6] text-[#93000a] dark:bg-red-950/40 dark:text-red-300 border border-red-500/10">
            Critical
          </span>
        );
      case 'High':
        return (
          <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-[#ffdbce] text-[#802a00] dark:bg-amber-950/40 dark:text-amber-300 border border-amber-500/10">
            High
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            Medium
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Panel */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className={`text-2xl font-extrabold tracking-tight ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
            Fraud Insights
          </h2>
          <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-[#444653]'}`}>
            Anomaly Analysis & Pattern Detection
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
              <Search size={14} />
            </span>
            <input 
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search clusters or patterns..."
              className={`text-xs pl-9 pr-4 py-2 rounded-lg border outline-none focus:ring-1 w-56 ${
                isDark 
                  ? 'bg-slate-900 border-slate-700 text-slate-300 focus:border-cyan-500' 
                  : 'bg-white border-[#c4c5d5] text-slate-700 focus:border-[#1e40af]'
              }`}
            />
          </div>
        </div>
      </div>

      {/* KPI Row cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1 */}
        <div className={`p-4 border rounded-xl flex flex-col justify-between h-28 ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <div className="flex justify-between items-start leading-none">
            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Total Anomalies Detected</span>
            <Flame size={14} className="text-amber-500" />
          </div>
          <div>
            <span className={`text-2xl font-extrabold pb-1 block leading-none ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
              {alerts.length}
            </span>
            <span className="text-[10px] font-bold text-red-500">Dataset target size</span>
          </div>
        </div>

        {/* KPI 2 */}
        <div className={`p-4 border rounded-xl flex flex-col justify-between h-28 ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <div className="flex justify-between items-start leading-none">
            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Critical Risk Targets</span>
            <Group size={14} className="text-[#3b82f6]" />
          </div>
          <div>
            <span className={`text-2xl font-extrabold pb-1 block leading-none ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
              {alerts.filter(a => a.riskScore >= 75).length}
            </span>
            <span className="text-[10px] font-bold text-slate-400">Score &gt;= 75 / 100</span>
          </div>
        </div>

        {/* KPI 3 */}
        <div className={`p-4 border rounded-xl flex flex-col justify-between h-28 ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <div className="flex justify-between items-start leading-none">
            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Model Pattern Score</span>
            <Target size={14} className="text-indigo-500" />
          </div>
          <div>
            <span className={`text-2xl font-extrabold pb-1 block leading-none ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
              {alerts.length > 0 ? (alerts.reduce((acc, a) => acc + a.confidenceVal, 0) / alerts.length).toFixed(1) + "%" : "97.7%"}
            </span>
            <span className="text-[10px] font-bold text-emerald-500">Mean target confidence</span>
          </div>
        </div>

        {/* KPI 4 */}
        <div className={`p-4 border rounded-xl flex flex-col justify-between h-28 ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <div className="flex justify-between items-start leading-none">
            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Outlier Mitigation Rate</span>
            <ShieldCheck size={14} className="text-emerald-500" />
          </div>
          <div>
            <span className={`text-2xl font-extrabold pb-1 block leading-none ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
              {alerts.length > 0 ? ((alerts.filter(a => a.status !== 'Open').length / alerts.length) * 100).toFixed(1) + "%" : "0.0%"}
            </span>
            <span className="text-[10px] font-bold text-slate-400">{alerts.filter(a => a.status === 'Open').length} pending review</span>
          </div>
        </div>
      </div>

      {/* Main Analysis Section grid layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Scatter Plot Chart Module (2 cols) */}
        <div className={`p-5 border rounded-xl lg:col-span-2 flex flex-col min-h-[380px] relative ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <div className="flex justify-between items-center mb-5 border-b border-slate-300 dark:border-slate-800 pb-2">
            <h3 className={`text-sm font-bold tracking-tight ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
              Anomaly Analysis
            </h3>
            
            <div className="flex items-center gap-3 text-[10px] font-bold text-slate-400">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[#1e40af] dark:bg-cyan-500/60"></span> Normal Points
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[#ba1a1a] dark:bg-red-400 border border-white"></span> Outlier Points
              </span>
            </div>
          </div>

          {/* Interactive responsive SVG coordinates mapping */}
          <div className="flex-1 flex flex-col justify-end">
            <div className="h-60 relative border-l border-b border-slate-300 dark:border-slate-800 flex items-center justify-center">
              
              {/* Y coordinates helpers */}
              <div className="absolute left-[-24px] top-0 bottom-0 justify-between flex flex-col text-[9px] font-bold text-slate-400 py-1 font-mono">
                <span>1.0</span>
                <span>0.5</span>
                <span>0.0</span>
              </div>

              {/* High-Polish SVG grid mapping coordinates */}
              <svg className="w-full h-full relative z-10 p-2" viewBox="0 0 300 220" preserveAspectRatio="none">
                {/* Horizontal reference dashed guides */}
                <line x1="0" y1="50" x2="300" y2="50" stroke={isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'} strokeDasharray="3 3"/>
                <line x1="0" y1="120" x2="300" y2="120" stroke={isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'} strokeDasharray="3 3"/>
                <line x1="0" y1="180" x2="300" y2="180" stroke={isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'} strokeDasharray="3 3"/>

                {/* Normal nodes list map */}
                {normalPoints.map((pt, i) => (
                  <circle 
                    key={`norm-${i}`}
                    cx={pt.x}
                    cy={pt.y}
                    r="4.5"
                    fill={isDark ? '#06b6d4' : '#1e40af'}
                    className="cursor-pointer transition-all hover:scale-145 opacity-60 hover:opacity-100"
                    onMouseEnter={() => setHoveredPoint(pt.label)}
                    onMouseLeave={() => setHoveredPoint(null)}
                  />
                ))}

                {/* Outliers nodes list map */}
                {outlierPoints.map((pt, i) => (
                  <g key={`out-group-${i}`}>
                    <circle 
                      cx={pt.x}
                      cy={pt.y}
                      r="6.5"
                      fill="#ef4444"
                      stroke="#ffffff"
                      strokeWidth="1.5"
                      className="cursor-pointer transition-all hover:scale-135 error-glow origin-center"
                      onMouseEnter={() => setHoveredPoint(pt.label)}
                      onMouseLeave={() => setHoveredPoint(null)}
                    />
                    <text
                      x={pt.x}
                      y={pt.y}
                      dx="10"
                      dy="3"
                      fill={isDark ? '#67e8f9' : '#1e40af'}
                      fontSize="6.5"
                      fontWeight="bold"
                      fontFamily="monospace"
                      className="pointer-events-none opacity-90 hidden sm:block"
                    >
                      {pt.accountNo.replace('ACC-TGT-', 'TGT-')}
                    </text>
                  </g>
                ))}
              </svg>

              {/* Tooltip render */}
              {hoveredPoint && (
                <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-slate-900 border border-slate-700 text-cyan-200 text-xs px-3 py-1.5 rounded-lg z-20 shadow-md">
                  {hoveredPoint}
                </div>
              )}
            </div>

            {/* X coordinates indicators */}
            <div className="flex justify-between text-[9px] font-bold text-slate-400 mt-2 font-mono px-2">
              <span>Transaction Vol</span>
              <span>Velocity Amplitude</span>
              <span>Composite Risk Score</span>
            </div>
          </div>
        </div>

        {/* High Risk Clusters Panel (1 col) */}
        <div className={`p-4 border rounded-xl flex flex-col justify-between min-h-[380px] ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <div className="border-b border-slate-300 dark:border-slate-800 pb-2 mb-3">
            <h3 className={`text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
              High-Risk Clusters
            </h3>
          </div>

          <div className="flex-1 space-y-3.5 overflow-y-auto max-h-64 pr-1">
            {filteredClusters.map((fc) => (
              <div 
                key={fc.id}
                className={`p-3 rounded-lg border leading-normal transition-all hover:bg-slate-300/10 ${
                  isDark ? 'bg-slate-950/40 border-slate-850' : 'bg-[#f4f2fc] border-[#c4c5d5]/50'
                }`}
              >
                <div className="flex justify-between items-center mb-1.5 leading-none">
                  <span className="font-bold text-xs">{fc.id}</span>
                  {getClusterSeverityChip(fc.severity)}
                </div>
                <p className="text-[11px] text-slate-400 mb-2 leading-relaxed">{fc.description}</p>
                <div className="flex justify-between text-[10px] text-slate-400/90 font-bold font-mono">
                  <span>{fc.entitiesCount} Entities matched</span>
                  <span className="text-red-500">Score: {fc.score.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>

          <button 
            onClick={() => setLimitClusters(!limitClusters)}
            className={`w-full py-2 border rounded-lg text-xs font-bold transition-all duration-300 hover:bg-slate-200/40 mt-4 leading-none ${
              isDark ? 'border-slate-800 hover:bg-slate-800 text-slate-300' : 'border-[#c4c5d5] text-slate-600'
            }`}
          >
            {limitClusters ? "View All Clusters" : "View Less Clusters"}
          </button>
        </div>
      </div>

      {/* Bottom logging outlier events standard table */}
      <div className={`border rounded-xl spill-hidden ${
        isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
      }`}>
        <div className="p-4 border-b border-slate-300 dark:border-slate-800 flex justify-between items-center bg-transparent">
          <h3 className={`text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            Recent Outlier Events
          </h3>
          <button 
            onClick={handleExportOutliers}
            className={`flex items-center gap-1.5 text-xs text-sky-600 dark:text-cyan-400 hover:underline leading-none font-sans`}
          >
            <Download size={13} />
            <span>Export Data</span>
          </button>
        </div>

        <div className="overflow-x-auto w-full table-scroll">
          <table className="w-full text-left border-collapse text-xs whitespace-nowrap">
            <thead>
              <tr className={`border-b ${isDark ? 'bg-slate-900/60 border-slate-800' : 'bg-[#f4f2fc] border-[#c4c5d5]'}`}>
                <th className="p-3.5 font-semibold text-slate-400 uppercase tracking-widest font-mono">Target ID</th>
                <th className="p-3.5 font-semibold text-slate-400 uppercase tracking-widest font-mono">Detection Time</th>
                <th className="p-3.5 font-semibold text-slate-400 uppercase tracking-widest font-mono">Account / Pattern Type</th>
                <th className="p-3.5 font-semibold text-slate-400 uppercase tracking-widest font-mono">Risk Score</th>
                <th className="p-3.5 font-semibold text-slate-400 uppercase tracking-widest font-mono text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-300/40 dark:divide-slate-800/60">
              {filteredOutliers.map((a) => (
                <tr key={a.id} className="hover:bg-slate-300/10 dark:hover:bg-slate-800/10 transition-colors h-12">
                  <td className="p-3 text-sky-600 dark:text-cyan-400 font-bold font-mono tracking-wide">{a.id}</td>
                  <td className="p-3 text-slate-450 font-mono font-semibold">{a.timestamp}</td>
                  <td className="p-3 font-semibold text-slate-650 dark:text-slate-300">
                    Mule Account Target (Acct: {a.accountNumber})
                  </td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      a.riskScore >= 75 
                        ? 'bg-red-500/10 text-red-500 border border-red-500/10' 
                        : a.riskScore >= 50
                          ? 'bg-amber-500/10 text-amber-500 border border-amber-500/10'
                          : 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/10'
                    }`}>
                      {a.riskScore >= 75 ? 'Critical' : a.riskScore >= 50 ? 'High' : 'Low'} ({a.riskScore}/100)
                    </span>
                  </td>
                  <td className="p-3 text-center">
                    <button 
                      onClick={() => onSelectAlert(a.id)}
                      className="text-sky-600 dark:text-cyan-400 font-bold hover:underline transition-all"
                    >
                      Review Case
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
