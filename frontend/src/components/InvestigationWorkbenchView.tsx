import React, { useState, useEffect, useMemo } from 'react';
import { Alert, AnalystNote, SystemTheme, TriageDecision } from '../types';
import { fageApi, CorrelateResponse, SimilarCasesResponse } from '../services/api';
import { usePaginatedAlerts } from '../hooks/useFageApi';
import { mapApiAlert } from '../utils/mapAlert';
import { formatINR } from '../utils/format';
import { NetworkGraph } from './NetworkGraph';
import { 
  Filter, 
  ArrowUpDown, 
  Clock, 
  User, 
  FileText, 
  Sparkles, 
  Hourglass, 
  AlertCircle,
  ShieldAlert,
  Activity,
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  XCircle,
  Sliders,
  Brain,
  ListChecks,
  GitCompare,
  Layers
} from 'lucide-react';

interface InvestigationWorkbenchViewProps {
  activeAlert: Alert;
  notes: Record<string, AnalystNote[]>;
  onAddNote: (id: string, noteText: string) => void;
  onUpdateStatus: (id: string, status: 'Open' | 'Escalated' | 'Closed' | 'Investigating') => void;
  onUpdateAssignment?: (id: string, assignee: string) => void;
  theme: SystemTheme;
  alerts?: Alert[];
  onSelectAlert?: (id: string) => void;
  dataSource?: import('../types').DataSourceType;
  isBackendOnline?: boolean;
}

export default function InvestigationWorkbenchView({
  activeAlert,
  notes,
  onAddNote,
  onUpdateStatus,
  alerts: alertsProp,
  onSelectAlert,
  theme,
  dataSource = 'live-all',
  isBackendOnline = true,
}: InvestigationWorkbenchViewProps) {
  
  const [noteContent, setNoteContent] = useState('');
  const [sarLoading, setSarLoading] = useState(false);
  const [sarReport, setSarReport] = useState<string | null>(activeAlert.sar_report || null);
  const [feedbackStatus, setFeedbackStatus] = useState<'idle' | 'submitting' | 'submitted'>('idle');
  const [feedbackType, setFeedbackType] = useState<'TP' | 'FP' | null>(null);
  const [triageLoading, setTriageLoading] = useState(false);
  const [triageDecisionState, setTriageDecisionState] = useState<TriageDecision | null>(activeAlert.triageDecision || null);
  const [plainLanguageLoading, setPlainLanguageLoading] = useState(false);
  const [plainLanguageText, setPlainLanguageText] = useState<string | null>(null);

  
  
  
  
  const [correlateData, setCorrelateData] = useState<CorrelateResponse | null>(null);
  const [correlateLoading, setCorrelateLoading] = useState(false);
  const [similarCases, setSimilarCases] = useState<SimilarCasesResponse | null>(null);
  const [similarCasesLoading, setSimilarCasesLoading] = useState(false);
  const [alertFeatures, setAlertFeatures] = useState<Record<string, any> | null>(null);
  const [featuresLoading, setFeaturesLoading] = useState(false);

  useEffect(() => {
    setCorrelateData(null);
    setSimilarCases(null);
    setAlertFeatures(null);
    setCorrelateLoading(true);
    setSimilarCasesLoading(true);
    setFeaturesLoading(true);

    fageApi.correlateAlert(activeAlert.id)
      .then(res => setCorrelateData(res))
      .catch(err => {
        console.error('Failed to fetch /correlate for investigation summary:', err);
        setCorrelateData(null);
      })
      .finally(() => setCorrelateLoading(false));

    fageApi.similarCases(activeAlert.id, 5)
      .then(res => setSimilarCases(res))
      .catch(err => {
        console.error('Failed to fetch /similar-cases:', err);
        setSimilarCases(null);
      })
      .finally(() => setSimilarCasesLoading(false));

    fageApi.getAlertFeatures(activeAlert.id)
      .then(res => setAlertFeatures(res.features))
      .catch(err => {
        console.error('Failed to fetch /features:', err);
        setAlertFeatures(null);
      })
      .finally(() => setFeaturesLoading(false));
  }, [activeAlert.id]);

  useEffect(() => {
    setNoteContent('');
    setSarLoading(false);
    setSarReport(activeAlert.sar_report || null);
    setFeedbackStatus('idle');
    setFeedbackType(null);
    setTriageLoading(false);
    setTriageDecisionState(activeAlert.triageDecision || null);

    if (!activeAlert.triageDecision && activeAlert.confidenceInterval && activeAlert.confidenceInterval.lower !== null && activeAlert.confidenceInterval.upper !== null && activeAlert.confidenceInterval.width !== null && activeAlert.hasRealExplainability) {
      setTriageLoading(true);
      fageApi.evaluateTriage({
        risk_score: activeAlert.riskScore,
        ci_lower: activeAlert.confidenceInterval.lower,
        ci_upper: activeAlert.confidenceInterval.upper,
        evadable: Boolean(activeAlert.evasionResistance?.evadable_within_search),
        pu_probability: activeAlert.pu_probability ?? (activeAlert.riskScore / 100),
        account_id: activeAlert.accountNumber || activeAlert.id
      })
        .then(res => {
          if (res && res.triage_evaluation) {
            setTriageDecisionState(res.triage_evaluation);
          } else {
            setTriageDecisionState(null);
          }
        })
        .catch(err => {
          console.error("Failed to evaluate triage policy via /triage-eval:", err);
          setTriageDecisionState(null);
        })
        .finally(() => {
          setTriageLoading(false);
        });
    }
  }, [activeAlert.id, activeAlert.confidenceInterval, activeAlert.evasionResistance, activeAlert.hasRealExplainability, activeAlert.pu_probability, activeAlert.riskScore, activeAlert.accountNumber, activeAlert.triageDecision]);

  const sourceFilter = dataSource === 'live-target' ? 'target' as const
    : dataSource === 'live-dataset' ? 'dataset' as const
    : undefined;

  const { alerts: fetchedSidebarAlerts } = usePaginatedAlerts({
    source_filter: sourceFilter,
    page: 1,
    pageSize: 50,
    enabled: !alertsProp && isBackendOnline,
  });

  const sidebarAlerts = useMemo(() => {
    const base = alertsProp ?? fetchedSidebarAlerts.map(mapApiAlert);
    if (!alertsProp && activeAlert && !base.some(a => a.id === activeAlert.id)) {
      return [activeAlert, ...base];
    }
    return base;
  }, [alertsProp, fetchedSidebarAlerts, activeAlert]);
  const sortedAlerts = [...sidebarAlerts].sort((a, b) => b.riskScore - a.riskScore);
  const effectiveTriageDecision = triageDecisionState || activeAlert.triageDecision;
  const effectiveTriageAction = effectiveTriageDecision?.triage_action || activeAlert.triage_action;
  const effectivePuProb = effectiveTriageDecision?.pu_probability ?? activeAlert.pu_probability;

  
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea') return;

      const idx = sortedAlerts.findIndex(a => a.id === activeAlert.id);
      if (e.key === 'j' || e.key === 'J' || e.key === 'ArrowDown') {
        e.preventDefault();
        if (idx < sortedAlerts.length - 1 && onSelectAlert) {
          onSelectAlert(sortedAlerts[idx + 1].id);
        }
      } else if (e.key === 'k' || e.key === 'K' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (idx > 0 && onSelectAlert) {
          onSelectAlert(sortedAlerts[idx - 1].id);
        }
      } else if (e.key === 'e' || e.key === 'E') {
        e.preventDefault();
        onUpdateStatus(activeAlert.id, 'Escalated');
      } else if (e.key === 'c' || e.key === 'C') {
        e.preventDefault();
        onUpdateStatus(activeAlert.id, 'Closed');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeAlert.id, sortedAlerts, onSelectAlert, onUpdateStatus]);

  const handleUpdateStatus = async (status: 'Open' | 'Escalated' | 'Closed' | 'Investigating') => {
    if (noteContent) {
      onAddNote(activeAlert.id, noteContent);
      setNoteContent('');
    }
    onUpdateStatus(activeAlert.id, status);
  };

  const handleEscalate = () => {
    onUpdateStatus(activeAlert.id, 'Escalated');
  };

  const handleGeneratePlainLanguage = async () => {
    setPlainLanguageLoading(true);
    try {
      const res = await fageApi.explainPlainLanguage(activeAlert.id);
      setPlainLanguageText(res.explanation);
    } catch (err) {
      console.error('Failed to generate plain language explanation', err);
    } finally {
      setPlainLanguageLoading(false);
    }
  };

  const handleFeedback = async (isTruePositive: boolean) => {
    setFeedbackStatus('submitting');
    setFeedbackType(isTruePositive ? 'TP' : 'FP');
    try {
      await fageApi.submitFeedback({
        alert_id: activeAlert.id,
        label: isTruePositive ? 'TP' : 'FP',
        trigger_recalibration: true
      });
      setFeedbackStatus('submitted');
    } catch (e) {
      console.error(e);
      setFeedbackStatus('idle');
      setFeedbackType(null);
    }
  };

  const handleGenerateSAR = async () => {
    setSarLoading(true);
    try {
      const res = await fageApi.generateSAR(activeAlert.id);
      setSarReport(res.sar_report);
    } catch (e) {
      console.error(e);
      setSarReport("Error generating AI SAR report.");
    } finally {
      setSarLoading(false);
    }
  };

  const formatTimeAgo = (alert: typeof activeAlert) => {
    
    const raw = alert.dateOpened || alert.timestamp;
    if (!raw || raw === 'Recent' || raw === 'Just now') return raw || 'Recent';
    const parsed = Date.parse(raw);
    if (isNaN(parsed)) return alert.timestamp; 
    const ms = Date.now() - parsed;
    const mins = Math.floor(ms / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins} mins ago`;
    return `${Math.floor(mins / 60)} hrs ago`;
  };

  return (
    <div className="absolute inset-0 flex flex-1 overflow-hidden bg-surface text-on-surface">
      {}
      <section className="w-[380px] flex flex-col border-r border-outline-variant bg-surface-container-lowest shrink-0">
        <div className="p-4 border-b border-outline-variant flex justify-between items-center bg-surface-container">
          <h2 className="text-sm font-bold uppercase tracking-wider text-on-surface-variant">Alert Queue</h2>
          <div className="flex gap-2">
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {sortedAlerts.map(alert => {
            const isActive = activeAlert.id === alert.id;
            const scoreClass = alert.riskScore >= 80 ? 'text-error' : (alert.riskScore >= 50 ? 'text-tertiary' : 'text-on-primary-container');
            const statusClass = alert.status === 'Investigating' || alert.status === 'Escalated' 
              ? 'bg-error-container text-on-error-container' 
              : 'bg-surface-container-high text-on-surface-variant';

            return (
              <div 
                key={alert.id}
                onClick={() => onSelectAlert && onSelectAlert(alert.id)}
                className={`p-4 border-b border-outline-variant transition-colors cursor-pointer group ${
                  isActive ? 'bg-secondary-container/20 border-l-4 border-primary' : 'hover:bg-surface-container border-l-4 border-transparent'
                }`}
              >
                <div className="flex justify-between mb-1">
                  <span className={`mono-text text-xs font-medium uppercase ${isActive ? 'text-primary' : 'text-on-surface-variant group-hover:text-primary'}`}>
                    {alert.id.substring(0, 12)}
                  </span>
                  <span className={`text-xs font-bold ${scoreClass}`}>
                    Score: {alert.riskScore}
                  </span>
                </div>
                
                <div className="flex justify-between items-end">
                  <div>
                    <div className="text-[10px] text-on-surface-variant flex items-center gap-1.5 mb-2">
                      <Clock size={12} />
                      {formatTimeAgo(alert)}
                    </div>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-tighter ${statusClass}`}>
                      {alert.status}
                    </span>
                  </div>
                  <div className="text-[11px] text-on-surface font-medium">{formatINR(alert.transactionAmount)}</div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {}
      <section className="flex-1 min-w-0 bg-surface flex flex-col overflow-y-auto custom-scrollbar relative">
        {}
        <div className="p-8 border-b border-outline-variant shrink-0">
          <div className="flex justify-between items-start mb-4">
            <div className="flex-1 min-w-0 pr-4">
              <div className="flex items-center gap-3 mb-2 flex-wrap">
                <h1 className="mono-text text-3xl font-black tracking-tight break-all">{activeAlert.id}</h1>
                {activeAlert.riskScore >= 80 && (
                  <span className="px-3 py-1 bg-error text-on-error text-[11px] font-black uppercase rounded-full">Critical Risk</span>
                )}
              </div>
              <p className="text-on-surface-variant text-sm">Detection Date: {activeAlert.dateOpened
                ? (() => { const d = new Date(activeAlert.dateOpened); return isNaN(d.getTime()) ? activeAlert.timestamp : d.toUTCString(); })()
                : activeAlert.timestamp}</p>
            </div>
            <div className="flex flex-col items-center">
              <div className="relative w-20 h-20">
                <svg className="w-full h-full transform -rotate-90">
                  <circle className="text-surface-container-highest" cx="40" cy="40" fill="transparent" r="36" stroke="currentColor" strokeWidth="6"></circle>
                  <circle 
                    className={activeAlert.riskScore >= 80 ? "text-error" : "text-primary"} 
                    cx="40" cy="40" fill="transparent" r="36" stroke="currentColor" 
                    strokeDasharray="226" 
                    strokeDashoffset={226 - (226 * activeAlert.riskScore) / 100} 
                    strokeWidth="6"
                    style={{ transition: 'stroke-dashoffset 1s ease-out' }}
                  ></circle>
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-xl font-black text-on-surface">{activeAlert.riskScore}</span>
                  <span className="text-[8px] text-on-surface-variant uppercase font-bold">Score</span>
                </div>
              </div>
            </div>
          </div>
          
          {}
          <div className="mb-6 flex items-center justify-between px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-lg text-xs text-on-surface-variant">
            <div className="flex items-center gap-4 font-mono">
              <span><kbd className="px-1.5 py-0.5 bg-surface border border-outline rounded text-[10px] font-bold text-on-surface">J</kbd> / <kbd className="px-1.5 py-0.5 bg-surface border border-outline rounded text-[10px] font-bold text-on-surface">K</kbd> Next/Prev Alert</span>
              <span><kbd className="px-1.5 py-0.5 bg-surface border border-outline rounded text-[10px] font-bold text-on-surface">E</kbd> Escalate</span>
              <span><kbd className="px-1.5 py-0.5 bg-surface border border-outline rounded text-[10px] font-bold text-on-surface">C</kbd> Close</span>
            </div>
            <span className="text-[11px] font-bold text-primary tracking-wide">SOC OPERATOR TRIAGE MODE ACTIVE</span>
          </div>

          {}
          {effectiveTriageAction && (
            <div className={`mb-6 p-4 rounded-xl border flex items-center justify-between stitch-glass-card ${
              effectiveTriageAction === 'FAST_TRACK_FREEZE'
                ? 'border-red-500/50 text-red-200'
                : effectiveTriageAction === 'PRIORITY_MANUAL_REVIEW'
                ? 'border-amber-500/50 text-amber-200'
                : effectiveTriageAction === 'INDEPENDENT_SIGNAL_CHECK'
                ? 'border-purple-500/50 text-purple-200'
                : 'border-slate-700 text-slate-300'
            }`}>
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <ShieldAlert className={
                  effectiveTriageAction === 'FAST_TRACK_FREEZE' ? 'text-red-400 shrink-0' :
                  effectiveTriageAction === 'PRIORITY_MANUAL_REVIEW' ? 'text-amber-400 shrink-0' :
                  effectiveTriageAction === 'INDEPENDENT_SIGNAL_CHECK' ? 'text-purple-400 shrink-0' : 'text-slate-400 shrink-0'
                } size={22} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-black tracking-wider uppercase truncate">
                    Operational Triage Route: {effectiveTriageAction.replace(/_/g, ' ')}
                  </div>
                  <div className="text-[11px] opacity-80 mt-0.5">
                    {effectiveTriageDecision?.rationale ? effectiveTriageDecision.rationale : (
                      <>
                        {effectiveTriageAction === 'FAST_TRACK_FREEZE' && 'High confidence positive with narrow CI and robust evasion resistance. Immediate freeze recommended.'}
                        {effectiveTriageAction === 'PRIORITY_MANUAL_REVIEW' && 'Model boundary uncertainty or wide confidence interval detected. Requires priority analyst review.'}
                        {effectiveTriageAction === 'INDEPENDENT_SIGNAL_CHECK' && 'Fragile signal detected. Check independent telemetry sources before locking account.'}
                        {effectiveTriageAction === 'STANDARD_MONITORING' && 'Standard low/moderate risk monitoring queue.'}
                      </>
                    )}
                  </div>
                </div>
              </div>
              {effectivePuProb !== undefined && effectivePuProb !== null && (
                <div className="text-right shrink-0 ml-4 pl-4 border-l border-outline-variant/30">
                  <div className="text-[10px] uppercase font-bold text-on-surface-variant">Calibrated PU Prob</div>
                  <div className="text-sm font-mono font-black text-on-surface">{((effectivePuProb ?? 0) * 100).toFixed(1)}%</div>
                </div>
              )}
            </div>
          )}

          {}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 p-6 bg-surface-container rounded-xl">
            <div>
              <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1 tracking-widest">Transaction Amount</p>
              <p className="text-lg font-bold text-on-surface">{formatINR(activeAlert.transactionAmount)}</p>
            </div>
            <div>
              <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1 tracking-widest">Type / Reason</p>
              <p className="text-sm font-bold text-on-surface line-clamp-2">{activeAlert.type}</p>
            </div>
            <div>
              <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1 tracking-widest">Receiver Account</p>
              <div className="flex items-center gap-1.5">
                <User size={14} className="text-primary" />
                <p className="text-sm font-bold text-on-surface">{activeAlert.receiverAccountId}</p>
              </div>
            </div>
            <div>
              <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1 tracking-widest">Account ID</p>
              <p className="mono-text text-lg font-bold text-on-surface">{activeAlert.accountNumber}</p>
            </div>
          </div>

          {}
          <div className="mt-6 grid grid-cols-1 gap-6 p-6 bg-surface-container rounded-xl">
            <h3 className="flex items-center gap-2 text-[10px] text-on-surface-variant uppercase font-bold tracking-widest">
              <Layers size={14} className="text-primary" /> Dataset Account Attributes (Raw)
            </h3>
            {featuresLoading ? (
               <div className="text-xs text-on-surface-variant italic py-2 flex items-center gap-2">
                 <div className="relative w-4 h-4 flex items-center justify-center">
                   <div className="absolute inset-0 border-[1.5px] border-primary border-t-transparent rounded-full animate-spin"></div>
                   <span className="text-[8px] font-bold text-primary">₹</span>
                 </div>
                 Loading dataset features...
               </div>
            ) : alertFeatures && Object.keys(alertFeatures).length > 0 ? (
               <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 max-h-48 overflow-y-auto custom-scrollbar pr-2">
                 {Object.entries(alertFeatures).filter(([_, v]) => v !== null && v !== 0 && v !== '').slice(0, 100).map(([key, value]) => (
                   <div key={key}>
                     <p className="text-[9px] text-on-surface-variant uppercase font-bold truncate" title={key}>{key}</p>
                     <p className="text-xs font-mono text-on-surface truncate" title={String(value)}>{String(value)}</p>
                   </div>
                 ))}
               </div>
            ) : (
               <div className="text-xs text-on-surface-variant italic py-2">No raw features available for this account.</div>
            )}
          </div>
        </div>

        {/* AI Investigation Summary -- shown FIRST, before SHAP/graph drill-downs, mirroring
            how a fraud analyst actually triages: read the summary, see why, see recommended
            actions, THEN drill into raw evidence if needed. */}
        <div className="px-8 pt-8 shrink-0">
          <div className="bg-surface-container border border-outline-variant rounded-xl p-6 mb-2">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Brain size={20} className="text-primary" />
                <h2 className="text-sm font-black uppercase tracking-wider text-on-surface">AI Investigation Summary</h2>
              </div>
              <button 
                onClick={handleGeneratePlainLanguage}
                disabled={plainLanguageLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high border border-outline-variant hover:bg-surface-container-highest transition-colors disabled:opacity-50 text-xs font-bold text-on-surface"
              >
                {plainLanguageLoading ? (
                  <div className="relative w-3.5 h-3.5 flex items-center justify-center">
                    <div className="absolute inset-0 border-[1.5px] border-primary border-t-transparent rounded-full animate-spin"></div>
                  </div>
                ) : <Brain size={14} />}
                Explain in Plain Language
              </button>
            </div>
            
            {plainLanguageText && (
              <div className="mb-6 p-4 bg-primary/10 border border-primary/20 rounded-lg">
                <div className="text-[10px] uppercase font-bold text-primary tracking-widest mb-2">Plain Language Explanation</div>
                <div className="text-sm text-on-surface whitespace-pre-wrap">{plainLanguageText}</div>
              </div>
            )}

            {correlateLoading && (
              <div className="text-xs text-on-surface-variant italic py-4 flex items-center gap-2">
                <div className="relative w-5 h-5 flex items-center justify-center">
                  <div className="absolute inset-0 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
                  <span className="text-[10px] font-bold text-primary">₹</span>
                </div>
                Generating investigation summary...
              </div>
            )}

            {!correlateLoading && !correlateData?.investigation_summary && (
              <div className="text-xs text-on-surface-variant italic py-4">
                No investigation summary available for this alert yet.
              </div>
            )}

            {!correlateLoading && correlateData?.investigation_summary && (() => {
              const summary = correlateData.investigation_summary;
              return (
                <div className="space-y-6">
                  {/* Risk score + decomposition */}
                  <div className="flex flex-wrap items-center gap-6">
                    <div>
                      <div className="text-[10px] uppercase font-bold text-on-surface-variant tracking-widest mb-1">Risk Score</div>
                      <div className="text-3xl font-black text-on-surface">{summary.risk_score_pct}%</div>
                                          </div>
                    <div className="flex-1 min-w-[220px]">
                      <div className="text-[10px] uppercase font-bold text-on-surface-variant tracking-widest mb-2">
                        Risk Decomposition
                      </div>
                      <div className="flex items-center gap-2 text-xs mb-1">
                        <span className="w-14 shrink-0 text-on-surface-variant">Model</span>
                        <div className="flex-1 h-2.5 bg-surface-container-highest rounded-full overflow-hidden">
                          <div className="h-full bg-primary rounded-full" style={{ width: `${summary.risk_decomposition.model_pct}%` }} />
                        </div>
                        <span className="w-12 text-right font-bold text-on-surface">{summary.risk_decomposition.model_pct}%</span>
                      </div>
                      {summary.risk_decomposition.rules_pct > 0 && (
                        <div className="flex items-center gap-2 text-xs mb-1">
                          <span className="w-14 shrink-0 text-on-surface-variant">Rules</span>
                          <div className="flex-1 h-2.5 bg-surface-container-highest rounded-full overflow-hidden">
                            <div className="h-full bg-tertiary rounded-full" style={{ width: `${summary.risk_decomposition.rules_pct}%` }} />
                          </div>
                          <span className="w-12 text-right font-bold text-on-surface">{summary.risk_decomposition.rules_pct}%</span>
                        </div>
                      )}
                      {summary.risk_decomposition.network_simulation_indicator && (
                        <div className="text-[10px] text-on-surface-variant italic mt-1">
                          Network (Investigation Simulation layer, not included above):{' '}
                          {summary.risk_decomposition.network_simulation_indicator.circular_flow_detected ? 'circular flow detected' : 'no circular flow'},{' '}
                          {summary.risk_decomposition.network_simulation_indicator.suspicious_neighbor_count} suspicious neighbor(s)
                        </div>
                      )}
                    </div>
                  </div>

                  {}
                  <div>
                    <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">
                      <Layers size={14} className="text-primary" /> Why this account?
                    </h3>
                    <p className="text-sm text-on-surface mb-3">{summary.assessment}</p>
                    <ul className="space-y-2">
                      {summary.evidence.map((e, i) => (
                        <li key={i} className="flex items-start gap-2 text-xs text-on-surface bg-surface-container-low border border-outline-variant rounded-lg p-3">
                          <CheckCircle2 size={14} className="text-primary shrink-0 mt-0.5" />
                          <span>{e.text}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {}
                  <div>
                    <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">
                      <ListChecks size={14} className="text-primary" /> Recommended Actions
                    </h3>
                    <ul className="space-y-1.5">
                      {summary.recommended_actions.map((a, i) => (
                        <li key={i} className="flex items-center gap-2 text-xs font-bold text-on-surface">
                          <CheckCircle2 size={14} className="text-primary shrink-0" /> {a}
                        </li>
                      ))}
                    </ul>
                    {summary.triage_rationale && (
                      <p className="text-[11px] text-on-surface-variant italic mt-2">{summary.triage_rationale}</p>
                    )}
                  </div>

                  <p className="text-[10px] text-on-surface-variant italic border-t border-outline-variant pt-3">
                    {summary.data_provenance_note}
                  </p>
                </div>
              );
            })()}
          </div>

          {}
          <div className="bg-surface-container border border-outline-variant rounded-xl p-6 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <GitCompare size={18} className="text-primary" />
              <h2 className="text-sm font-black uppercase tracking-wider text-on-surface">Similar Past Cases</h2>
            </div>
            {similarCasesLoading && (
              <div className="text-xs text-on-surface-variant italic py-2 flex items-center gap-2">
                <div className="relative w-4 h-4 flex items-center justify-center">
                  <div className="absolute inset-0 border-[1.5px] border-primary border-t-transparent rounded-full animate-spin"></div>
                  <span className="text-[8px] font-bold text-primary">₹</span>
                </div>
                Finding similar cases...
              </div>
            )}
            {!similarCasesLoading && (!similarCases || similarCases.similar_cases.length === 0) && (
              <div className="text-xs text-on-surface-variant italic py-2">No comparable past cases found yet.</div>
            )}
            {!similarCasesLoading && similarCases && similarCases.similar_cases.length > 0 && (
              <div className="space-y-2">
                {similarCases.similar_cases.map(c => (
                  <div key={c.alert_id} className="flex items-center justify-between bg-surface-container-low border border-outline-variant rounded-lg p-3 text-xs">
                    <div className="flex items-center gap-3">
                      <span className="mono-text font-bold text-on-surface">{c.alert_id}</span>
                      <span className="text-on-surface-variant">{c.status}</span>
                    </div>
                    <span className="font-black text-primary">{c.similarity_pct}% similar</span>
                  </div>
                ))}
                <p className="text-[10px] text-on-surface-variant italic pt-1">{similarCases.note}</p>
              </div>
            )}
          </div>
        </div>

        {}
        <div className="p-8 grid grid-cols-1 lg:grid-cols-2 gap-8 shrink-0">
          {}
          <div className="space-y-8">
            <div>
              <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-on-surface mb-4">
                <FileText size={18} className="text-primary" />
                Operator Notes
              </h3>
              <textarea 
                className="w-full bg-surface-container-low border border-outline-variant rounded-lg p-4 text-sm text-on-surface focus:outline-none focus:ring-1 focus:ring-primary h-32 placeholder:text-on-surface-variant/30 custom-scrollbar" 
                placeholder="Type investigation notes here..."
                value={noteContent}
                onChange={(e) => setNoteContent(e.target.value)}
              ></textarea>
            </div>
            
            {notes[activeAlert.id] && notes[activeAlert.id].length > 0 && (
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-2">Previous Notes</h4>
                {notes[activeAlert.id].map(n => (
                  <div key={n.id} className="bg-surface-container-low p-3 rounded-lg border border-outline-variant text-xs">
                    <div className="flex justify-between text-[10px] text-on-surface-variant mb-1 font-bold">
                      <span>{n.author}</span>
                      <span>{n.timestamp}</span>
                    </div>
                    <div className="text-on-surface">{n.content}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {}
          <div className="space-y-8">
            <div>
              <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-on-surface mb-4">
                <ShieldAlert size={18} className="text-primary" />
                Key Risk Drivers
              </h3>
              {activeAlert.hasRealExplainability && activeAlert.keyRiskDrivers.length > 0 ? (
                <div className="space-y-2">
                  {activeAlert.keyRiskDrivers.map((d, i) => (
                    <div key={i} className="flex items-center justify-between bg-surface-container-low border border-outline-variant rounded-lg p-3">
                      <div className="flex items-center gap-2">
                        {d.direction === 'increases_risk' ? (
                          <TrendingUp size={14} className="text-error" />
                        ) : (
                          <TrendingDown size={14} className="text-primary" />
                        )}
                        <span className="mono-text text-xs font-bold text-on-surface">Anonymized Feature {d.feature}</span>
                      </div>
                      <span className={`text-xs font-bold ${d.direction === 'increases_risk' ? 'text-error' : 'text-primary'}`}>
                        {d.direction === 'increases_risk' ? '+' : ''}{(typeof d.importance_attribution === 'number' ? d.importance_attribution : 0).toFixed(4)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="bg-surface-container-low border border-outline-variant border-dashed rounded-lg p-4 text-xs text-on-surface-variant italic">
                  No SHAP explanation available for this alert (likely created before explainability was enabled, or the model service was unreachable at detection time).
                </div>
              )}
            </div>

            <div>
              <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-on-surface mb-4">
                <Activity size={18} className="text-primary" />
                Model Confidence
              </h3>
              {activeAlert.confidenceInterval && activeAlert.confidenceInterval.width !== null ? (
                <div className="bg-surface-container-low border border-outline-variant rounded-lg p-4 text-xs text-on-surface-variant">
                  <p className="text-on-surface font-bold mb-1 flex flex-wrap items-center gap-1">
                    <span>90% interval:</span>
                    <span className="inline-block whitespace-nowrap font-mono text-cyan-600 dark:text-cyan-400">{((activeAlert.confidenceInterval?.lower ?? 0) * 100).toFixed(1)}%</span>
                    <span>–</span>
                    <span className="inline-block whitespace-nowrap font-mono text-cyan-600 dark:text-cyan-400">{((activeAlert.confidenceInterval?.upper ?? 0) * 100).toFixed(1)}%</span>
                  </p>
                  <p className="mt-1 leading-relaxed">{activeAlert.confidenceInterval.note}</p>
                </div>
              ) : (
                <div className="bg-surface-container-low border border-outline-variant border-dashed rounded-lg p-4 text-xs text-on-surface-variant italic">
                  Confidence interval unavailable for this alert.
                </div>
              )}
            </div>

            {activeAlert.evasionResistance && (
              <div>
                <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-on-surface mb-4">
                  <AlertCircle size={18} className="text-primary" />
                  Evasion Resistance
                </h3>
                <div className="bg-surface-container-low border border-outline-variant rounded-lg p-4 text-xs text-on-surface-variant">
                  {activeAlert.evasionResistance.interpretation}
                </div>
              </div>
            )}

            <div>
              <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-on-surface mb-4">
                <ShieldAlert size={18} className="text-primary" />
                Confidence-Routed Triage Evaluation
              </h3>
              {triageLoading ? (
                <div className="bg-surface-container-low border border-outline-variant border-dashed rounded-lg p-4 text-xs text-on-surface-variant italic flex items-center gap-2">
                  <div className="relative w-4 h-4 flex items-center justify-center mr-1">
                    <div className="absolute inset-0 border-[1.5px] border-primary border-t-transparent rounded-full animate-spin"></div>
                    <span className="text-[8px] font-bold text-primary">₹</span>
                  </div>
                  Evaluating multi-dimensional triage policy via /triage-eval...
                </div>
              ) : effectiveTriageDecision && effectiveTriageDecision.triage_action ? (
                <div className={`border rounded-lg p-4 text-xs ${
                  effectiveTriageDecision.triage_action === 'FAST_TRACK_FREEZE'
                    ? 'bg-red-500/10 border-red-500/40 text-red-100 dark:text-red-200'
                    : effectiveTriageDecision.triage_action === 'PRIORITY_MANUAL_REVIEW'
                    ? 'bg-amber-500/10 border-amber-500/40 text-amber-100 dark:text-amber-200'
                    : effectiveTriageDecision.triage_action === 'INDEPENDENT_SIGNAL_CHECK'
                    ? 'bg-purple-500/10 border-purple-500/40 text-purple-100 dark:text-purple-200'
                    : 'bg-surface-container-low border-outline-variant text-on-surface-variant'
                }`}>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="font-mono font-bold text-[11px] uppercase tracking-wider px-2 py-0.5 rounded bg-surface/60 border border-outline-variant">
                      Action: {effectiveTriageDecision.triage_action.replace(/_/g, ' ')}
                    </span>
                    {effectiveTriageDecision.priority_tier && (
                      <span className="font-bold text-[10px] uppercase tracking-wide opacity-90">
                        Priority: {effectiveTriageDecision.priority_tier}
                      </span>
                    )}
                  </div>
                  {effectiveTriageDecision.rationale ? (
                    <p className="mt-1 leading-relaxed font-medium">
                      {effectiveTriageDecision.rationale}
                    </p>
                  ) : (
                    <p className="mt-1 leading-relaxed italic opacity-80">
                      Triage action assigned based on model confidence and risk profile.
                    </p>
                  )}
                  {effectiveTriageDecision.ci_width !== undefined && (
                    <div className="mt-3 pt-2 border-t border-outline-variant/30 flex flex-wrap gap-4 font-mono text-[10px] opacity-80">
                      <span>CI Width: {(effectiveTriageDecision.ci_width * 100).toFixed(1)}%</span>
                      {effectiveTriageDecision.evadable !== undefined && (
                        <span>Evadable: {effectiveTriageDecision.evadable ? 'Yes' : 'No'}</span>
                      )}
                      {effectiveTriageDecision.pu_probability !== undefined && (
                        <span>PU Prob: {(effectiveTriageDecision.pu_probability * 100).toFixed(1)}%</span>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-surface-container-low border border-outline-variant border-dashed rounded-lg p-4 text-xs text-on-surface-variant italic">
                  Confidence-routed triage evaluation unavailable for this alert (requires valid confidence interval and explainability metrics).
                </div>
              )}
            </div>

            {}
            <div className="mt-2">
              <NetworkGraph alertId={activeAlert.id} theme={theme} />
            </div>

            <div>
              <div className="flex justify-between items-center mb-4">
                <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-on-surface">
                  <Sparkles size={18} className="text-primary animate-pulse" />
                  AI-Generated SAR Draft
                </h3>
                {!sarReport && (
                  <button 
                    className="px-3 py-1 text-xs bg-primary text-on-primary rounded font-bold transition-opacity hover:opacity-90 disabled:opacity-50"
                    disabled={sarLoading}
                    onClick={handleGenerateSAR}
                  >
                    {sarLoading ? 'Generating...' : 'Generate SAR'}
                  </button>
                )}
              </div>
              
              {sarReport ? (
                <div className="bg-surface-container-low border border-outline-variant rounded-lg p-6 font-mono text-xs leading-relaxed text-on-surface-variant overflow-y-auto max-h-[400px] whitespace-pre-wrap custom-scrollbar">
                  {sarReport}
                </div>
              ) : (
                <div className="bg-surface-container-low border border-outline-variant border-dashed rounded-lg p-6 text-xs text-on-surface-variant italic flex items-center justify-center h-32">
                  {sarLoading ? (
                    <div className="flex items-center gap-2">
                      <div className="relative w-4 h-4 flex items-center justify-center">
                        <div className="absolute inset-0 border-[1.5px] border-primary border-t-transparent rounded-full animate-spin"></div>
                        <span className="text-[8px] font-bold text-primary">₹</span>
                      </div>
                      AI is analyzing evidence and drafting SAR...
                    </div>
                  ) : 'No SAR report generated yet.'}
                </div>
              )}
            </div>

            {}
            <div className="bg-surface-container rounded-xl border border-outline-variant p-4 flex flex-col gap-4">
              <div className="flex items-start md:items-center gap-3 w-full min-w-0">
                <div className="p-2.5 rounded-lg bg-tertiary/10 text-tertiary shrink-0 mt-1 md:mt-0">
                  <Sliders size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-xs font-bold text-on-surface uppercase tracking-wider flex flex-wrap items-center gap-2 break-words">
                    Closed-Loop Active Learning Feedback
                    {feedbackStatus === 'submitted' && (
                      <span className="text-[10px] font-mono text-tertiary px-2 py-0.5 rounded bg-tertiary/10 flex items-center gap-1">
                        <CheckCircle2 size={12} /> PU Engine c-Factor Adjusted
                      </span>
                    )}
                  </h4>
                  <p className="text-xs text-on-surface-variant mt-1 break-words">
                    {feedbackStatus === 'submitted'
                      ? `Recorded ${feedbackType === 'TP' ? 'True Positive (Confirmed Fraud)' : 'False Positive (Dismissed)'}. Online SPY & Elkan-Noto probabilities recalibrated.`
                      : 'Provide ground-truth verification to adjust Elkan-Noto c-factor frequency correction and SPY thresholds dynamically.'}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-end gap-2 w-full">
                <button
                  onClick={() => handleFeedback(true)}
                  disabled={feedbackStatus !== 'idle'}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all ${
                    feedbackStatus === 'submitted' && feedbackType === 'TP'
                      ? 'bg-error text-on-error ring-2 ring-error/50'
                      : 'bg-error/10 text-error border border-error/30 hover:bg-error/20 disabled:opacity-50'
                  }`}
                >
                  <CheckCircle2 size={14} />
                  {feedbackStatus === 'submitting' && feedbackType === 'TP' ? 'Calibrating...' : 'Confirm Fraud (TP)'}
                </button>
                <button
                  onClick={() => handleFeedback(false)}
                  disabled={feedbackStatus !== 'idle'}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all ${
                    feedbackStatus === 'submitted' && feedbackType === 'FP'
                      ? 'bg-tertiary text-on-tertiary ring-2 ring-tertiary/50'
                      : 'bg-surface-container-high text-on-surface border border-outline-variant hover:bg-surface-container-highest disabled:opacity-50'
                  }`}
                >
                  <XCircle size={14} />
                  {feedbackStatus === 'submitting' && feedbackType === 'FP' ? 'Calibrating...' : 'Dismiss (FP)'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {}
        <div className="mt-auto p-6 border-t border-outline-variant bg-surface-container-low flex justify-end items-center gap-4 sticky bottom-0 z-10 shrink-0">
          <button 
            className={`px-6 py-2 rounded-lg border transition-colors text-sm font-bold flex items-center gap-2 ${
              activeAlert.status === 'Closed'
                ? 'bg-surface-container-highest border-outline-variant text-on-surface-variant cursor-default opacity-70'
                : 'border-outline-variant text-on-surface-variant hover:bg-surface-container-high'
            }`}
            onClick={() => {
              if (activeAlert.status !== 'Closed') handleUpdateStatus('Closed');
            }}
            disabled={activeAlert.status === 'Closed'}
          >
            {activeAlert.status === 'Closed' ? <CheckCircle2 size={16} /> : null}
            {activeAlert.status === 'Closed' ? 'Resolved' : 'Mark Resolved'}
          </button>
          <button 
            className={`px-6 py-2 rounded-lg border transition-colors text-sm font-bold flex items-center gap-2 ${
              activeAlert.status === 'Investigating' 
                ? 'bg-primary/20 border-primary text-primary cursor-default' 
                : 'bg-surface-container-highest border-outline-variant text-on-surface hover:bg-surface-container-highest/80'
            }`}
            onClick={() => {
              if (activeAlert.status !== 'Investigating') handleUpdateStatus('Investigating');
            }}
            disabled={activeAlert.status === 'Investigating'}
          >
            {activeAlert.status === 'Investigating' ? (
              <Activity size={14} className="text-primary" />
            ) : (
              <AlertCircle size={14} />
            )}
            {activeAlert.status === 'Investigating' ? 'Investigating' : 'Investigate'}
          </button>
          <button 
            className="px-8 py-2 rounded-lg bg-error text-on-error hover:opacity-90 transition-opacity text-sm font-bold shadow-lg shadow-error/10"
            onClick={() => handleUpdateStatus('Escalated')}
          >
            Block / Escalate
          </button>
        </div>
      </section>
    </div>
  );
}
