import React, { useState } from 'react';
import { 
  Building, 
  AlertTriangle, 
  BellRing, 
  TrendingUp, 
  TrendingDown, 
  ArrowUpRight, 
  FileText, 
  Calendar,
  Eye,
  Activity,
  Cpu,
  Send,
  Check,
  DollarSign,
  Target
} from 'lucide-react';
import { Alert, SystemTheme, ViewMode, DataSourceType } from '../types';
import { useRiskScore } from '../hooks/useFageApi';

interface DashboardViewProps {
  alerts: Alert[];
  onSelectAlert: (id: string) => void;
  theme: SystemTheme;
  onRefreshAlerts?: () => void;
  dataSource: DataSourceType;
  setDataSource: (source: DataSourceType) => void;
  isBackendOnline: boolean;
  apiAlertsCount: number;
  apiTargetCount: number;
  apiDatasetCount: number;
  apiError: string | null;
}

export default function DashboardView({ 
  alerts, 
  onSelectAlert, 
  theme, 
  onRefreshAlerts,
  dataSource,
  setDataSource,
  isBackendOnline,
  apiAlertsCount,
  apiTargetCount,
  apiDatasetCount,
  apiError
}: DashboardViewProps) {
  const isDark = theme === 'sovereign';
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [timeframe, setTimeframe] = useState<string>('7 Days');

  // Real-time scoring state and evaluation handlers
  const { evaluate, result: scoreResult, loading: scoringLoading, error: scoringError, reset: resetScoring } = useRiskScore();
  const [simAmount, setSimAmount] = useState('12000');
  const [simSender, setSimSender] = useState('ACC-4901');
  const [simReceiver, setSimReceiver] = useState('ACC-8832');
  const [simAccountAge, setSimAccountAge] = useState('5');
  const [simOrigin, setSimOrigin] = useState('US');
  const [simDest, setSimDest] = useState('US');
  const [simInternational, setSimInternational] = useState(false);

  const handleSimulate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await evaluate({
        amount: parseFloat(simAmount) || 0,
        sender_id: simSender,
        receiver_id: simReceiver,
        account_age_days: parseInt(simAccountAge) || 0,
        origin_country: simOrigin,
        destination_country: simDest,
        is_international: simInternational
      });
      if (onRefreshAlerts) {
        setTimeout(() => {
          onRefreshAlerts();
        }, 300);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Dynamic Risk Distribution calculations
  const riskStats = React.useMemo(() => {
    const total = alerts.length || 1;
    const lowCount = alerts.filter(a => a.riskScore < 50).length;
    const medCount = alerts.filter(a => a.riskScore >= 50 && a.riskScore < 75).length;
    const highCount = alerts.filter(a => a.riskScore >= 75).length;
    
    const lowPct = Math.round((lowCount / total) * 100);
    const medPct = Math.round((medCount / total) * 100);
    const highPct = 100 - lowPct - medPct;
    
    return { lowPct, medPct, highPct };
  }, [alerts]);

  // Dynamic Alert Category/Distribution calculations
  const alertStats = React.useMemo(() => {
    const total = alerts.length || 1;
    let muleCount = 0;
    let networkCount = 0;
    let velocityCount = 0;
    
    alerts.forEach(a => {
      const typeStr = (a.type || '').toLowerCase();
      if (typeStr.includes('mule') || typeStr.includes('target') || typeStr.includes('fraud')) {
        muleCount++;
      } else if (typeStr.includes('network') || typeStr.includes('ip') || typeStr.includes('proxy') || typeStr.includes('sanction') || typeStr.includes('ofac')) {
        networkCount++;
      } else {
        velocityCount++;
      }
    });
    
    // Fallback split if empty to match historical design baseline
    if (muleCount === 0 && networkCount === 0 && velocityCount === 0) {
      muleCount = Math.round(total * 0.15);
      networkCount = Math.round(total * 0.25);
      velocityCount = total - muleCount - networkCount;
    }
    
    const velocityPct = Math.round((velocityCount / total) * 100);
    const networkPct = Math.round((networkCount / total) * 100);
    const mulePct = 100 - velocityPct - networkPct;
    
    return {
      total,
      muleCount,
      networkCount,
      velocityCount,
      velocityPct,
      networkPct,
      mulePct
    };
  }, [alerts]);

  // Dynamic financial totals calculations
  const { totalRiskAmount, totalTargetAmount } = React.useMemo(() => {
    const totalRisk = alerts
      .filter(a => a.riskScore >= 75)
      .reduce((sum, a) => sum + a.balance, 0);
      
    const totalTarget = alerts
      .filter(a => a.type === 'Mule Account')
      .reduce((sum, a) => sum + a.balance, 0);
      
    return { totalRiskAmount: totalRisk, totalTargetAmount: totalTarget };
  }, [alerts]);

  const formatCurrency = (val: number) => {
    if (val >= 1000000) {
      return `$${(val / 1000000).toFixed(2)}M`;
    }
    if (val >= 1000) {
      return `$${(val / 1000).toFixed(1)}k`;
    }
    return `$${val.toLocaleString()}`;
  };

  // Interactive fraud trend simulated data
  const trendData = [
    { day: 'Mon', short: 'M', value: 600, label: 'Mon: 600 txns' },
    { day: 'Tue', short: 'T', value: 450, label: 'Tue: 450 txns' },
    { day: 'Wed', short: 'W', value: 750, label: 'Wed: 750 txns' },
    { day: 'Thu', short: 'T', value: 550, label: 'Thu: 550 txns' },
    { day: 'Fri', short: 'F', value: 900, label: 'Fri: 900 (Spike Flagged)', isSpike: true },
    { day: 'Sat', short: 'S', value: 400, label: 'Sat: 400 txns' },
    { day: 'Sun', short: 'S', value: 300, label: 'Sun: 300 txns' },
  ];

  const criticalRecent = alerts
    .filter(a => a.riskScore > 80)
    .slice(0, 3);

  // SVG dimensions for Donut Chart
  const donutRadius = 40;
  const donutCircumference = 2 * Math.PI * donutRadius;
  
  // Dynamic segments representing Velocity, Network, Mule
  const segment1Dash = (alertStats.velocityPct / 100) * donutCircumference;
  const segment2Dash = (alertStats.networkPct / 100) * donutCircumference;
  const segment3Dash = (alertStats.mulePct / 100) * donutCircumference;

  const handleGenerateReport = () => {
    window.print();
  };

  return (
    <div className="space-y-6">
      {/* Header Info Panel */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className={`text-2xl font-extrabold tracking-tight ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
            Executive Dashboard
          </h2>
          <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-[#444653]'}`}>
            Overview of risk intelligence and mule account detection performance.
          </p>
        </div>
        
        <div className="flex flex-wrap items-center gap-3">
          {/* Connection Status Badge */}
          <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold border transition-colors ${
            isBackendOnline 
              ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-500' 
              : 'bg-amber-500/10 border-amber-500/25 text-amber-500'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full bg-current ${isBackendOnline ? 'animate-pulse' : ''}`} />
            {isBackendOnline ? 'Live API Connected' : 'Offline'}
          </div>

          {/* Data Stream Selector */}
          <div className="relative">
            <select
              value={dataSource}
              onChange={(e) => setDataSource(e.target.value as DataSourceType)}
              className={`appearance-none font-sans text-xs px-3 py-2 pr-8 rounded-lg outline-none cursor-pointer border transition-colors ${
                isDark 
                  ? 'bg-slate-900 border-slate-700 text-slate-350 focus:border-cyan-500' 
                  : 'bg-white border-[#c4c5d5] text-slate-700 focus:border-[#1e40af]'
              }`}
            >
              <option value="live-all" disabled={!isBackendOnline}>
                {isBackendOnline ? `Live: All Alerts (${apiAlertsCount})` : 'Live: All Alerts (Offline)'}
              </option>
              <option value="live-target" disabled={!isBackendOnline}>
                {isBackendOnline ? `Live: Mule Accounts (${apiTargetCount})` : 'Live: Mule Accounts (Offline)'}
              </option>
              <option value="live-dataset" disabled={!isBackendOnline}>
                {isBackendOnline ? `Live: Dataset Audits (${apiDatasetCount})` : 'Live: Dataset Audits (Offline)'}
              </option>
            </select>
            <Calendar size={13} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400" />
          </div>

          <div className="relative">
            <select 
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className={`appearance-none font-sans text-xs px-3 py-2 pr-8 rounded-lg outline-none cursor-pointer border ${
                isDark 
                  ? 'bg-slate-900 border-slate-700 text-slate-300 focus:border-cyan-500' 
                  : 'bg-white border-[#c4c5d5] text-slate-700 focus:border-[#1e40af]'
              }`}
            >
              <option>Last 7 Days</option>
              <option>Last 30 Days</option>
              <option>This Quarter</option>
            </select>
            <Calendar size={13} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400" />
          </div>

          <button 
            onClick={handleGenerateReport}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all duration-300 ${
              isDark 
                ? 'bg-cyan-500 hover:bg-cyan-600 text-[#051424] cyan-glow' 
                : 'bg-[#1e40af] hover:bg-opacity-90 text-white shadow-sm'
            }`}
          >
            <FileText size={14} />
            <span>Generate Report</span>
          </button>
        </div>
      </div>

      {/* Backend Connection Alert Banner */}
      {!isBackendOnline && (
        <div className={`p-4 border rounded-xl text-xs flex items-center justify-between transition-all duration-300 ${
          isDark 
            ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' 
            : 'bg-amber-50 border-amber-200 text-amber-700'
        }`}>
          <div className="flex items-center gap-2">
            <span className="text-sm">⚠️</span>
            <span>
              <strong>Backend Connection Issue:</strong> The FAGE FastAPI server on port 8000 is not responding.
              {apiError && <span className="block mt-1 font-mono bg-amber-500/5 p-1 rounded">Error details: {apiError}</span>}
              <span className="block mt-1">Start the backend service (by running <code>start.bat</code>) to restore live connectivity and view the dataset.</span>
            </span>
          </div>
          <button 
            onClick={() => onRefreshAlerts?.()} 
            className={`px-3 py-1.5 rounded-lg font-bold transition-all duration-200 ${
              isDark 
                ? 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300' 
                : 'bg-amber-100 hover:bg-amber-200 text-amber-800'
            }`}
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* KPI 1 */}
        <div className={`border rounded-xl p-4 relative overflow-hidden group transition-all duration-300 ${
          isDark 
            ? 'bg-slate-900/40 border-slate-800 text-slate-300' 
            : 'bg-white border-[#c4c5d5] text-slate-800 shadow-sm'
        }`}>
          <div className="absolute top-2 right-2 opacity-5 group-hover:opacity-10 transition-opacity duration-300 text-slate-400">
            <Building size={64} />
          </div>
          <p className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Accounts Analysed</p>
          <p className={`text-2xl font-extrabold mt-2 font-sans ${isDark ? 'text-slate-100' : 'text-[#00288e]'}`}>2.7k</p>
          <div className="flex items-center gap-2 mt-2">
            <TrendingUp size={14} className="text-emerald-500" />
            <span className="text-xs font-bold text-emerald-500">100%</span>
            <span className="text-[10px] text-slate-400 font-medium">dataset loaded</span>
          </div>
        </div>

        {/* KPI 2 */}
        <div className={`border rounded-xl p-4 relative overflow-hidden group transition-all duration-300 ${
          isDark 
            ? 'bg-slate-900/40 border-slate-800 text-slate-300' 
            : 'bg-white border-[#c4c5d5] text-slate-800 shadow-sm'
        }`}>
          <div className="absolute top-2 right-2 opacity-5 group-hover:opacity-10 transition-opacity duration-300 text-slate-400">
            <AlertTriangle size={64} />
          </div>
          <p className="text-[10px] uppercase font-bold tracking-wider text-slate-400">High-Risk Accounts</p>
          <p className="text-2xl font-extrabold mt-2 text-[#ba1a1a] font-sans">{alerts.filter(a => a.riskScore >= 50).length}</p>
          <div className="flex items-center gap-2 mt-2">
            <TrendingUp size={14} className="text-[#ba1a1a]" />
            <span className="text-xs font-bold text-[#ba1a1a]">+1.2%</span>
            <span className="text-[10px] text-slate-400 font-medium">vs last period</span>
          </div>
        </div>

        {/* KPI 3 */}
        <div className={`border rounded-xl p-4 relative overflow-hidden group transition-all duration-300 ${
          isDark 
            ? 'bg-slate-900/40 border-slate-800 text-slate-300' 
            : 'bg-white border-[#c4c5d5] text-slate-800 shadow-sm'
        }`}>
          <div className="absolute top-2 right-2 opacity-5 group-hover:opacity-10 transition-opacity duration-300 text-slate-400">
            <BellRing size={64} />
          </div>
          <p className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Critical Alerts</p>
          <p className="text-2xl font-extrabold mt-2 text-[#ba1a1a] font-sans">{alerts.filter(a => a.riskScore >= 75).length}</p>
          <div className="flex items-center gap-2 mt-2">
            <TrendingDown size={14} className="text-emerald-500" />
            <span className="text-xs font-bold text-emerald-500">-12.4%</span>
            <span className="text-[10px] text-slate-400 font-medium">vs last week</span>
          </div>
        </div>

        {/* KPI 4 */}
        <div className={`border rounded-xl p-4 relative overflow-hidden group transition-all duration-300 ${
          isDark 
            ? 'bg-slate-900/40 border-slate-800 text-slate-300' 
            : 'bg-white border-[#c4c5d5] text-slate-800 shadow-sm'
        }`}>
          <div className="absolute top-2 right-2 opacity-5 group-hover:opacity-10 transition-opacity duration-300 text-slate-400">
            <DollarSign size={64} />
          </div>
          <p className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Exposure at Risk</p>
          <p className={`text-2xl font-extrabold mt-2 font-sans ${isDark ? 'text-slate-100' : 'text-[#ba1a1a]'}`}>{formatCurrency(totalRiskAmount)}</p>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Risk/Critical balances</span>
          </div>
        </div>

        {/* KPI 5 */}
        <div className={`border rounded-xl p-4 relative overflow-hidden group transition-all duration-300 ${
          isDark 
            ? 'bg-slate-900/40 border-slate-800 text-slate-300' 
            : 'bg-white border-[#c4c5d5] text-slate-800 shadow-sm'
        }`}>
          <div className="absolute top-2 right-2 opacity-5 group-hover:opacity-10 transition-opacity duration-300 text-slate-400">
            <Target size={64} />
          </div>
          <p className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Target Fraud Volume</p>
          <p className={`text-2xl font-extrabold mt-2 font-sans ${isDark ? 'text-cyan-300' : 'text-[#00288e]'}`}>{formatCurrency(totalTargetAmount)}</p>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Dataset targets total</span>
          </div>
        </div>
      </div>

      {/* Main Charts area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left Column: Trend & Simulator (spans 2 cols) */}
        <div className="lg:col-span-2 flex flex-col gap-6 w-full">
          {/* Main interactive bar trend chart */}
          <div className={`border rounded-xl p-5 flex flex-col min-h-[340px] relative ${
            isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
          }`}>
            <div className="flex justify-between items-center mb-6">
              <div>
                <h3 className={`text-sm font-bold tracking-tight ${isDark ? 'text-slate-200' : 'text-[#1a1b22]'}`}>
                  Fraud Detection Trend
                </h3>
                <span className="text-[10px] text-slate-400">System incidents count (7d series)</span>
              </div>
              
              <div className="flex items-center gap-2 text-[10px] font-semibold text-slate-400">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#dde1ff]"></span> Normal Volume
                <span className="w-2.5 h-2.5 rounded-sm bg-gradient-to-t from-[#fee2e2] to-[#ba1a1a]"></span> Flagged Spike
              </div>
            </div>

            {/* Interactive Chart Core */}
            <div className="flex-1 flex flex-col justify-end">
              <div className="h-44 flex items-end justify-between px-1 relative">
                {/* Y Axis Gridlines and Markers */}
                <div className="absolute left-0 right-0 top-0 h-full flex flex-col justify-between pointer-events-none">
                  <div className="border-b border-dashed border-slate-300 dark:border-slate-800 w-full relative">
                    <span className="absolute -top-3.5 left-0 text-[9px] font-bold text-slate-400">1,000 txns</span>
                  </div>
                  <div className="border-b border-dashed border-slate-300 dark:border-slate-800 w-full relative">
                    <span className="absolute -top-3.5 left-0 text-[9px] font-bold text-slate-400">500 txns</span>
                  </div>
                  <div className="border-b border-dashed border-slate-300 dark:border-slate-800 w-full relative">
                    <span className="absolute -top-3.5 left-0 text-[10px] font-bold text-slate-400">0</span>
                  </div>
                </div>

                {/* Hover tooltip card overlay */}
                {selectedDay && (
                  <div className={`absolute top-4 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-lg text-xs font-bold leading-none z-30 shadow-md ${
                    selectedDay.includes('Spike') 
                      ? 'bg-[#ba1a1a] text-white' 
                      : (isDark ? 'bg-slate-800 text-cyan-300' : 'bg-slate-800 text-white')
                  }`}>
                    {selectedDay}
                  </div>
                )}

                {/* Chart Bars */}
                {trendData.map((d, index) => {
                  const heightPercent = `${(d.value / 1000) * 100}%`;
                  return (
                    <div 
                      key={index} 
                      className="flex flex-col items-center flex-1 group z-10 cursor-pointer"
                      onMouseEnter={() => setSelectedDay(d.label)}
                      onMouseLeave={() => setSelectedDay(null)}
                      onClick={() => setSelectedDay(d.label)}
                    >
                      <div className="w-9/12 bg-slate-300 dark:bg-slate-800 rounded-t-sm h-40 flex items-end overflow-hidden transition-all duration-200">
                        <div 
                          style={{ height: heightPercent }}
                          className={`w-full rounded-t-sm transition-all duration-300 cursor-pointer ${
                            d.isSpike 
                              ? 'bg-gradient-to-t from-[#fee2e2] to-[#ba1a1a] border-2 border-red-500 scale-102 error-glow' 
                              : (isDark ? 'bg-[#3755c3] hover:bg-cyan-500' : 'bg-[#dde1ff] hover:bg-[#1e40af]')
                          }`}
                        ></div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* X Axis Labels */}
              <div className="flex justify-between mt-3 text-[10px] font-bold text-slate-400 px-4">
                {trendData.map((d, index) => (
                  <span key={index} className="w-12 text-center">{d.day}</span>
                ))}
              </div>
            </div>
          </div>

          {/* Real-time Transaction Simulator */}
          <div className={`border rounded-xl p-5 flex flex-col justify-between ${
            isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
          }`}>
            <div className="flex items-center gap-2 mb-4 border-b border-slate-300 dark:border-slate-800 pb-2.5">
              <Activity size={14} className="text-cyan-500 animate-pulse" />
              <h3 className={`text-xs font-bold uppercase tracking-tight ${isDark ? 'text-slate-300' : 'text-[#757684]'}`}>
                Real-Time Simulator
              </h3>
            </div>

            {scoreResult ? (
              <div className="space-y-3 text-xs">
                <div className={`p-3 rounded-lg border text-center ${
                  scoreResult.scores.final_risk_score >= 75 
                    ? 'bg-red-500/10 border-red-500/25 text-red-500' 
                    : scoreResult.scores.final_risk_score >= 50
                    ? 'bg-amber-500/10 border-amber-500/25 text-amber-500'
                    : 'bg-emerald-500/10 border-emerald-500/25 text-emerald-500'
                }`}>
                  <span className="text-[10px] uppercase font-bold tracking-wider block mb-1">Decision: {scoreResult.categorizations.action_decision}</span>
                  <span className="text-3xl font-black">{scoreResult.scores.final_risk_score}</span>
                  <span className="text-[9px] block text-slate-400 mt-1">Score mapped from {Math.round(scoreResult.scores.base_ml_probability * 100)}% ML probability</span>
                </div>

                <div className="space-y-1.5 text-[11px] leading-tight">
                  <div className="flex justify-between">
                    <span className="text-slate-450">Transaction ID:</span>
                    <span className="font-mono font-bold text-slate-400">{scoreResult.transaction_id.slice(0, 15)}...</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-450">Risk Tier:</span>
                    <span className="font-bold">{scoreResult.categorizations.risk_tier}</span>
                  </div>
                  {scoreResult.rules_audit.triggered_rules_count > 0 && (
                    <div className="mt-2 text-red-400 font-medium">
                      <span>Triggered Rules:</span>
                      <ul className="list-disc pl-3.5 mt-0.5 space-y-0.5 text-[10px]">
                        {scoreResult.rules_audit.overrides.map((rule, idx) => (
                          <li key={idx}>{rule.rule_name}: {rule.reason}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <button 
                  onClick={resetScoring}
                  className="w-full py-1.5 border border-slate-700 hover:bg-slate-800 text-slate-350 rounded-lg font-bold text-xs mt-2 transition-colors"
                >
                  Score New Transaction
                </button>
              </div>
            ) : (
              <form onSubmit={handleSimulate} className="space-y-3.5 text-[11px]">
                {/* 2-column input layout on small, 3-column on desktop */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div className="flex flex-col gap-1">
                    <label className="text-slate-405 font-bold uppercase tracking-wide text-[9px]">Sender ID</label>
                    <input 
                      type="text" 
                      value={simSender} 
                      onChange={e => setSimSender(e.target.value)} 
                      className={`p-1.5 text-xs rounded border outline-none ${
                        isDark ? 'bg-slate-950 border-slate-800 text-slate-300 focus:border-cyan-500' : 'bg-white border-[#c4c5d5] text-slate-705'
                      }`}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-slate-405 font-bold uppercase tracking-wide text-[9px]">Receiver ID</label>
                    <input 
                      type="text" 
                      value={simReceiver} 
                      onChange={e => setSimReceiver(e.target.value)} 
                      className={`p-1.5 text-xs rounded border outline-none ${
                        isDark ? 'bg-slate-950 border-slate-800 text-slate-300 focus:border-cyan-500' : 'bg-white border-[#c4c5d5] text-slate-705'
                      }`}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-slate-405 font-bold uppercase tracking-wide text-[9px]">Amount ($)</label>
                    <input 
                      type="number" 
                      value={simAmount} 
                      onChange={e => setSimAmount(e.target.value)} 
                      className={`p-1.5 text-xs rounded border outline-none ${
                        isDark ? 'bg-slate-950 border-slate-800 text-slate-300 focus:border-cyan-500' : 'bg-white border-[#c4c5d5] text-slate-705'
                      }`}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-slate-405 font-bold uppercase tracking-wide text-[9px]">Acct Age (Days)</label>
                    <input 
                      type="number" 
                      value={simAccountAge} 
                      onChange={e => setSimAccountAge(e.target.value)} 
                      className={`p-1.5 text-xs rounded border outline-none ${
                        isDark ? 'bg-slate-950 border-slate-800 text-slate-300 focus:border-cyan-500' : 'bg-white border-[#c4c5d5] text-slate-705'
                      }`}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-slate-405 font-bold uppercase tracking-wide text-[9px]">Origin Country</label>
                    <input 
                      type="text" 
                      value={simOrigin} 
                      onChange={e => setSimOrigin(e.target.value)} 
                      className={`p-1.5 text-xs rounded border outline-none ${
                        isDark ? 'bg-slate-950 border-slate-800 text-slate-300 focus:border-cyan-500' : 'bg-white border-[#c4c5d5] text-slate-705'
                      }`}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-slate-405 font-bold uppercase tracking-wide text-[9px]">Dest Country</label>
                    <input 
                      type="text" 
                      value={simDest} 
                      onChange={e => setSimDest(e.target.value)} 
                      className={`p-1.5 text-xs rounded border outline-none ${
                        isDark ? 'bg-slate-950 border-slate-800 text-slate-300 focus:border-cyan-500' : 'bg-white border-[#c4c5d5] text-slate-705'
                      }`}
                    />
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mt-3 border-t border-slate-300 dark:border-slate-800/60 pt-3">
                  <div className="flex items-center gap-2">
                    <input 
                      type="checkbox" 
                      id="simInt" 
                      checked={simInternational} 
                      onChange={e => setSimInternational(e.target.checked)} 
                      className="cursor-pointer"
                    />
                    <label htmlFor="simInt" className="text-slate-405 font-bold uppercase tracking-wide text-[9px] cursor-pointer">International Transfer</label>
                  </div>

                  <button 
                    type="submit"
                    disabled={scoringLoading}
                    className={`px-5 py-2 rounded-lg font-bold text-xs flex items-center justify-center gap-1.5 transition-colors ${
                      isDark 
                        ? 'bg-cyan-500 hover:bg-cyan-600 text-[#051424] disabled:opacity-50' 
                        : 'bg-[#1e40af] hover:bg-opacity-95 text-white disabled:opacity-50'
                    }`}
                  >
                    <Cpu size={12} />
                    <span>{scoringLoading ? "Scoring..." : "Score Transaction"}</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>

        {/* Right Column: Distributions (1 col) */}
        <div className="flex flex-col gap-6 w-full">
          {/* Risk distribution progress block */}
          <div className={`border rounded-xl p-4 flex flex-col justify-between ${
            isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
          }`}>
            <h3 className={`text-xs font-bold tracking-tight mb-4 uppercase ${isDark ? 'text-slate-300' : 'text-[#757684]'}`}>
              Risk Distribution
            </h3>

            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-xs font-bold mb-1">
                  <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>Low Risk</span>
                  <span className="text-slate-400">{riskStats.lowPct}%</span>
                </div>
                <div className="w-full bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${riskStats.lowPct}%` }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-bold mb-1">
                  <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>Medium Risk</span>
                  <span className="text-slate-400">{riskStats.medPct}%</span>
                </div>
                <div className="w-full bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div className="bg-amber-500 h-full rounded-full" style={{ width: `${riskStats.medPct}%` }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-bold mb-1">
                  <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>High Risk</span>
                  <span className="text-slate-400">{riskStats.highPct}%</span>
                </div>
                <div className="w-full bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div className="bg-[#ba1a1a] h-full rounded-full" style={{ width: `${riskStats.highPct}%` }}></div>
                </div>
              </div>
            </div>
          </div>

          {/* Alert Distribution Donut Ring Chart */}
          <div className={`border rounded-xl p-4 flex flex-col justify-between ${
            isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
          }`}>
            <h3 className={`text-xs font-bold tracking-tight mb-2 uppercase ${isDark ? 'text-slate-300' : 'text-[#757684]'}`}>
              Alert Distribution
            </h3>

            <div className="flex items-center justify-center p-2 relative">
              <svg className="w-28 h-28 transform -rotate-90">
                {/* 60% segment (Velocity Blue) */}
                <circle 
                  cx="56" cy="56" r={donutRadius} 
                  fill="transparent" 
                  stroke={isDark ? '#0566d9' : '#1e40af'} 
                  strokeWidth="10" 
                  strokeDasharray={`${segment1Dash} ${donutCircumference - segment1Dash}`}
                  strokeDashoffset="0"
                />
                
                {/* 25% segment (Network Accent) */}
                <circle 
                  cx="56" cy="56" r={donutRadius} 
                  fill="transparent" 
                  stroke={isDark ? '#4cd7f6' : '#d0e1fb'} 
                  strokeWidth="10" 
                  strokeDasharray={`${segment2Dash} ${donutCircumference - segment2Dash}`}
                  strokeDashoffset={-segment1Dash}
                />
                
                {/* 15% segment (Mule Error) */}
                <circle 
                  cx="56" cy="56" r={donutRadius} 
                  fill="transparent" 
                  stroke={isDark ? '#ffb4ab' : '#ffdad6'} 
                  strokeWidth="10" 
                  strokeDasharray={`${segment3Dash} ${donutCircumference - segment3Dash}`}
                  strokeDashoffset={-(segment1Dash + segment2Dash)}
                />
              </svg>

              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className={`text-md font-extrabold ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>{alerts.length}</span>
                <span className="text-[9px] text-slate-400 uppercase font-medium">Total alerts</span>
              </div>
            </div>

            <div className="flex justify-center flex-wrap items-center gap-x-4 gap-y-1 text-[9px] font-bold text-slate-400 mt-2">
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[#1e40af] dark:bg-[#0566d9]"></span>
                <span>Velocity ({alertStats.velocityPct}%)</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[#d0e1fb] dark:bg-[#4cd7f6]"></span>
                <span>Network ({alertStats.networkPct}%)</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[#ffdad6] dark:bg-[#ffb4ab]"></span>
                <span>Mule ({alertStats.mulePct}%)</span>
              </div>
            </div>
          </div>
        </div>
      </div>


      {/* Bottom recent critical alerts list panel */}
      <div className={`border rounded-xl overflow-hidden ${
        isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
      }`}>
        <div className="p-4 border-b border-slate-300 dark:border-slate-800 flex justify-between items-center bg-transparent">
          <h3 className={`text-xs font-bold uppercase tracking-wider ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            Recent Critical Alerts
          </h3>
          <span className="text-[10px] text-slate-400 font-semibold font-sans">Active Live Feeds</span>
        </div>

        <div className="overflow-x-auto w-full table-scroll">
          <table className="w-full text-left border-collapse text-xs whitespace-nowrap">
            <thead>
              <tr className={`border-b ${isDark ? 'bg-slate-900/60 border-slate-800' : 'bg-[#f4f2fc] border-[#c4c5d5]'}`}>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-wider">Account ID</th>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-wider">Alert Type</th>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-wider">Risk Score</th>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-wider">Timestamp</th>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-wider font-sans">Status</th>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-wider text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-300/40 dark:divide-slate-800/60">
              {criticalRecent.map((a) => (
                <tr 
                  key={a.id} 
                  className={`hover:bg-slate-300/10 dark:hover:bg-slate-850/50 transition-colors group h-12`}
                >
                  <td className="p-3 font-bold text-sky-600 dark:text-cyan-400">{a.accountNumber}</td>
                  <td className="p-3 font-semibold text-slate-600 dark:text-slate-300">{a.type}</td>
                  <td className="p-3 font-mono font-bold text-[#ba1a1a]">{a.riskScore}/100</td>
                  <td className="p-3 text-slate-400">{a.timestamp}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      a.status === 'Open' 
                        ? 'bg-[#ffdad6] text-[#93000a] dark:bg-red-950/40 dark:text-red-300 border border-red-500/20' 
                        : 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                    }`}>
                      {a.status}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <button 
                      onClick={() => onSelectAlert(a.id)}
                      className="p-1 px-2 hover:bg-slate-400/20 dark:hover:bg-slate-700 rounded transition-colors text-[#1e40af] dark:text-cyan-300"
                      title="Inspect Workbench"
                    >
                      <Eye size={15} />
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
