import React, { useState } from 'react';
import { 
  Download, 
  HelpCircle, 
  TrendingUp, 
  Activity, 
  GitCommit,
  Check,
  ShieldCheck,
  AlertTriangle,
  Cpu
} from 'lucide-react';
import { SHAPDriver, SystemTheme } from '../types';
import { shapDrivers } from '../data';
import { useModelMetrics } from '../hooks/useFageApi';

interface ModelPerformanceViewProps {
  theme: SystemTheme;
}

export default function ModelPerformanceView({ theme }: ModelPerformanceViewProps) {
  const isDark = theme === 'sovereign';
  const [selectedModel, setSelectedModel] = useState<string>('XGBoost');
  const [activeMatrixCell, setActiveMatrixCell] = useState<string | null>(null);

  const { data: metricsData } = useModelMetrics();

  // Find metrics for selected model
  const metrics = React.useMemo(() => {
    if (metricsData && metricsData[selectedModel]) {
      return metricsData[selectedModel];
    }
    // Hardcoded fallback metrics matching original design
    return {
      accuracy: 0.982,
      precision: 0.952,
      recall: 0.964,
      f1: 0.952,
      roc_auc: 0.942,
      pr_auc: 0.931,
      confusion_matrix: [[945210, 1152], [214, 4892]]
    };
  }, [metricsData, selectedModel]);

  const fpr = React.useMemo(() => {
    const cm = metrics.confusion_matrix;
    const tn = cm[0][0];
    const fp = cm[0][1];
    const den = tn + fp;
    return den > 0 ? (fp / den) * 100 : 0.0;
  }, [metrics]);

  const tnRate = React.useMemo(() => {
    const cm = metrics.confusion_matrix;
    const tn = cm[0][0];
    const fp = cm[0][1];
    const den = tn + fp;
    return den > 0 ? (tn / den) * 100 : 0.0;
  }, [metrics]);

  const tpRate = React.useMemo(() => {
    const cm = metrics.confusion_matrix;
    const fn = cm[1][0];
    const tp = cm[1][1];
    const den = fn + tp;
    return den > 0 ? (tp / den) * 100 : 0.0;
  }, [metrics]);

  const fnRate = React.useMemo(() => {
    const cm = metrics.confusion_matrix;
    const fn = cm[1][0];
    const tp = cm[1][1];
    const den = fn + tp;
    return den > 0 ? (fn / den) * 100 : 0.0;
  }, [metrics]);

  const handleExportMetrics = () => {
    const csvContent = "data:text/csv;charset=utf-8," 
      + [
          "Model,Accuracy,FPR,Recall,F1-Score",
          `XGBoost,${(metrics.accuracy*100).toFixed(2)}%,${fpr.toFixed(2)}%,${(metrics.recall*100).toFixed(2)}%,${metrics.f1.toFixed(3)}`
        ].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `FAGE_Model_Performance_Metrics_${selectedModel}_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // SVG Coordinates for Precision-Recall Curve
  // Simulates a smooth arc from top-left (0, 30) down to bottom-right (260, 180)
  const curvePoints = "20,20 80,24 140,35 200,65 240,110 260,180";

  return (
    <div className="space-y-6">
      {/* Header Info Panel */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className={`text-2xl font-extrabold tracking-tight ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
            Model Performance
          </h2>
          <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-[#444653]'}`}>
            Evaluate accuracy, precision, and threshold distributions for risk intelligence engines.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className={`appearance-none font-sans text-xs px-3 py-2 pr-8 rounded-lg outline-none cursor-pointer border ${
                isDark 
                  ? 'bg-slate-900 border-slate-700 text-slate-300 focus:border-cyan-500' 
                  : 'bg-white border-[#c4c5d5] text-slate-700 focus:border-[#1e40af]'
              }`}
            >
              {metricsData ? (
                Object.keys(metricsData).map((mName) => (
                  <option key={mName} value={mName}>Model: {mName}</option>
                ))
              ) : (
                <>
                  <option value="XGBoost">Model: XGBoost</option>
                  <option value="LightGBM">Model: LightGBM</option>
                  <option value="RandomForest">Model: RandomForest</option>
                  <option value="ExtraTrees">Model: ExtraTrees</option>
                  <option value="LogisticRegression">Model: LogisticRegression</option>
                  <option value="IsolationForest">Model: IsolationForest</option>
                  <option value="Ensemble">Model: Ensemble</option>
                </>
              )}
            </select>
            <Cpu size={13} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400" />
          </div>

          <button 
            onClick={handleExportMetrics}
            className={`flex items-center gap-2 px-4 py-2 border rounded-lg text-xs font-bold transition-all duration-300 h-9 ${
              isDark 
                ? 'bg-transparent border-slate-800 hover:bg-slate-800 text-slate-300' 
                : 'bg-white border-[#c4c5d5] text-slate-700 hover:bg-100 shadow-sm'
            }`}
          >
            <Download size={14} />
            <span>Export Metrics</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs font-sans">
        {/* Metric 1 */}
        <div className={`p-4 border rounded-xl flex flex-col justify-between h-28 ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Classification Accuracy</span>
          <div>
            <span className={`text-2xl font-extrabold pb-0.5 block leading-none ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
              {(metrics.accuracy * 100).toFixed(2)}%
            </span>
            <span className="text-[10px] font-bold text-emerald-500 flex items-center leading-none">
              <TrendingUp size={11} className="mr-0.5" /> Stable performance
            </span>
          </div>
        </div>

        {/* Metric 2 */}
        <div className={`p-4 border rounded-xl flex flex-col justify-between h-28 ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 font-sans">False Positive Rate (FPR)</span>
          <div>
            <span className={`text-2xl font-extrabold pb-0.5 block leading-none ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
              {fpr.toFixed(2)}%
            </span>
            <span className="text-[10px] font-bold text-emerald-500 leading-none">Minimizes false flags</span>
          </div>
        </div>

        {/* Metric 3 */}
        <div className={`p-4 border rounded-xl flex flex-col justify-between h-28 ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">True Positive Rate (Recall)</span>
          <div>
            <span className={`text-2xl font-extrabold pb-0.5 block leading-none ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
              {(metrics.recall * 100).toFixed(2)}%
            </span>
            <span className="text-[10px] font-bold text-emerald-500 flex items-center leading-none">
              <TrendingUp size={11} className="mr-0.5" /> Strong detection rate
            </span>
          </div>
        </div>

        {/* Metric 4 */}
        <div className={`p-4 border rounded-xl flex flex-col justify-between h-28 ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Overall F1-Score Ratio</span>
          <div>
            <span className={`text-2xl font-extrabold pb-0.5 block leading-none ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
              {metrics.f1.toFixed(3)}
            </span>
            <span className="text-[10px] font-bold text-slate-400 leading-none">Stable across all cohorts</span>
          </div>
        </div>
      </div>

      {/* Main Charts block */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Precision-Recall curve panel */}
        <div className={`p-5 border rounded-xl flex flex-col min-h-[340px] relative ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <div className="flex justify-between items-center mb-5 border-b border-slate-300 dark:border-slate-800 pb-2">
            <div>
              <h3 className={`text-sm font-bold tracking-tight ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                ROC Precision-Recall Curve
              </h3>
              <span className="text-[10px] text-slate-400">Target AUC performance visualization metrics</span>
            </div>
            
            <span className="text-[10px] font-bold text-slate-400">Consensus threshold: 0.85</span>
          </div>

          <div className="flex-1 flex flex-col justify-end">
            <div className="h-56 relative border-l border-b border-slate-300 dark:border-slate-800 flex items-center justify-center p-2">
              
              {/* Reference Grid lines */}
              <div className="absolute inset-0 flex flex-col justify-between pointer-events-none py-1.5 px-0.5">
                <div className="border-b border-dashed border-slate-300 dark:border-slate-850 w-full relative">
                  <span className="absolute -top-3.5 left-1 text-[9px] font-bold text-slate-400">1.0 Precision</span>
                </div>
                <div className="border-b border-dashed border-slate-300 dark:border-slate-850 w-full relative">
                  <span className="absolute -top-3.5 left-1 text-[9px] font-bold text-slate-400">0.5</span>
                </div>
                <div className="border-b border-dashed border-slate-300 dark:border-slate-850 w-full relative">
                  <span className="absolute -top-3.5 left-1 text-[9px] font-bold text-slate-400">0.0</span>
                </div>
              </div>

              {/* Smooth curve rendered using vector SVGs */}
              <svg className="w-full h-full relative z-10 p-2 overflow-visible">
                {/* Precision curve line path */}
                <path 
                  d={`M ${curvePoints}`} 
                  fill="none" 
                  stroke={isDark ? '#3b82f6' : '#1e40af'} 
                  strokeWidth="3.5"
                  className="transition-all duration-1000"
                />

                {/* Shading fill underneath curve */}
                <path
                  d={`M 20,180 L ${curvePoints} L 260,180 Z`}
                  fill={isDark ? 'rgba(59, 130, 246, 0.05)' : 'rgba(30, 64, 175, 0.03)'}
                />

                {/* Highlight active balance threshold point */}
                <circle 
                  cx="140" cy="35"
                  r="6.5"
                  fill="#10b981"
                  stroke="#ffffff"
                  strokeWidth="2"
                  className="animate-pulse cursor-pointer shadow-md"
                  title="Optimal operating point: AUC = 0.942"
                />
              </svg>

              {/* Score pointer overlay legend absolute */}
              <div className="absolute top-1/2 left-1/3 flex items-center bg-emerald-950/40 border border-emerald-500/10 text-emerald-300 text-[10px] uppercase font-mono px-2 py-0.5 rounded shadow">
                <GitCommit size={11} className="mr-1 animate-spin-slow" />
                <span>AUC Operating Pivot: 0.942</span>
              </div>
            </div>

            <div className="flex justify-between mt-2.5 text-[9px] font-bold text-slate-400 font-mono px-2">
              <span>0.0 False Positive</span>
              <span>Recall Level</span>
              <span>1.0 Recall</span>
            </div>
          </div>
        </div>

        {/* Confusion Matrix grid panel */}
        <div className={`p-5 border rounded-xl flex flex-col justify-between ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <div className="border-b border-slate-300 dark:border-slate-800 pb-2 mb-4 flex justify-between items-center">
            <div>
              <h3 className={`text-sm font-bold tracking-tight ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                Confusion Matrix (Holdout Set)
              </h3>
              <span className="text-[10px] text-slate-400">Classification distribution for historical target batches</span>
            </div>
            <HelpCircle size={15} className="text-slate-400 hover:text-indigo-500 cursor-pointer" />
          </div>

          <div className="grid grid-cols-3 gap-2.5 max-w-sm mx-auto text-center py-2 text-xs font-sans">
            {/* Column Label block */}
            <div></div>
            <div className="font-bold text-[10px] uppercase text-slate-400 font-mono">Predicted Normal</div>
            <div className="font-bold text-[10px] uppercase text-slate-400 font-mono">Predicted Mule</div>

            {/* Row 1 */}
            <div className="font-bold text-[10px] uppercase text-slate-400 self-center font-mono">Actual Normal</div>
            
            {/* TN Block */}
            <div 
              onMouseEnter={() => setActiveMatrixCell(`TN: True Negative Rate = ${tnRate.toFixed(2)}% (${metrics.confusion_matrix[0][0].toLocaleString()} normal correctly kept)`)}
              onMouseLeave={() => setActiveMatrixCell(null)}
              className={`p-4 rounded-lg flex flex-col justify-center cursor-pointer border hover:scale-102 transition-transform duration-200 ${
                isDark ? 'bg-slate-950/40 border-slate-800' : 'bg-emerald-50 border-emerald-100'
              }`}
            >
              <Check size={14} className="mx-auto text-emerald-500 mb-1" />
              <span className={`font-black text-sm ${isDark ? 'text-emerald-400' : 'text-emerald-800'}`}>
                {metrics.confusion_matrix[0][0].toLocaleString()}
              </span>
              <span className="text-[8px] uppercase tracking-wider text-slate-400 font-bold mt-1">True Neg (TN)</span>
            </div>

            {/* FP Block */}
            <div 
              onMouseEnter={() => setActiveMatrixCell(`FP: False Alarm Rate = ${fpr.toFixed(2)}% (${metrics.confusion_matrix[0][1].toLocaleString()} normal flagged by model)`)}
              onMouseLeave={() => setActiveMatrixCell(null)}
              className={`p-4 rounded-lg flex flex-col justify-center cursor-pointer border hover:scale-102 transition-transform duration-200 ${
                isDark ? 'bg-slate-950/40 border-slate-800' : 'bg-rose-50 border-rose-100'
              }`}
            >
              <AlertTriangle size={14} className="mx-auto text-[#ba1a1a] mb-1" />
              <span className="font-black text-sm text-[#ba1a1a]">
                {metrics.confusion_matrix[0][1].toLocaleString()}
              </span>
              <span className="text-[8px] uppercase tracking-wider text-slate-400 font-bold mt-1">False Pos (FP)</span>
            </div>

            {/* Row 2 */}
            <div className="font-bold text-[10px] uppercase text-slate-400 self-center font-mono">Actual Mule</div>
            
            {/* FN Block */}
            <div 
              onMouseEnter={() => setActiveMatrixCell(`FN: Leakage Rate = ${fnRate.toFixed(2)}% (${metrics.confusion_matrix[1][0].toLocaleString()} suspicious went unflagged)`)}
              onMouseLeave={() => setActiveMatrixCell(null)}
              className={`p-4 rounded-lg flex flex-col justify-center cursor-pointer border hover:scale-102 transition-transform duration-200 ${
                isDark ? 'bg-slate-950/40 border-slate-800' : 'bg-orange-50 border-orange-100'
              }`}
            >
              <AlertTriangle size={14} className="mx-auto text-amber-500 mb-1" />
              <span className="font-black text-sm text-yellow-600 dark:text-amber-400">
                {metrics.confusion_matrix[1][0].toLocaleString()}
              </span>
              <span className="text-[8px] uppercase tracking-wider text-slate-400 font-bold mt-1">False Neg (FN)</span>
            </div>

            {/* TP Block */}
            <div 
              onMouseEnter={() => setActiveMatrixCell(`TP: Model Detection Rate = ${tpRate.toFixed(2)}% (${metrics.confusion_matrix[1][1].toLocaleString()} correct detections)`)}
              onMouseLeave={() => setActiveMatrixCell(null)}
              className={`p-4 rounded-lg flex flex-col justify-center cursor-pointer border hover:scale-102 transition-transform duration-200 ${
                isDark ? 'bg-slate-950/40 border-slate-800' : 'bg-emerald-50 border-emerald-100'
              }`}
            >
              <ShieldCheck size={14} className="mx-auto text-emerald-500 mb-1" />
              <span className={`font-black text-sm ${isDark ? 'text-emerald-400' : 'text-emerald-800'}`}>
                {metrics.confusion_matrix[1][1].toLocaleString()}
              </span>
              <span className="text-[8px] uppercase tracking-wider text-slate-400 font-bold mt-1">True Pos (TP)</span>
            </div>
          </div>

          {/* Precision stats status readout info card */}
          <div className="h-10 mt-3 flex items-center justify-center">
            {activeMatrixCell ? (
              <p className="text-xs font-semibold text-[#00288e] dark:text-cyan-300 font-mono select-none px-4 text-center leading-tight">
                {activeMatrixCell}
              </p>
            ) : (
              <p className="text-[10px] uppercase font-bold tracking-wider text-slate-400 select-none">
                Hover over blocks for rate indices details
              </p>
            )}
          </div>
        </div>
      </div>

    </div>
  );
}
