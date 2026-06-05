import React, { useState } from 'react';
import { 
  Download, 
  HelpCircle, 
  TrendingUp, 
  Cpu, 
  Database,
  ArrowRight,
  TrendingDown
} from 'lucide-react';
import { SHAPDriver, SystemTheme } from '../types';
import { shapDrivers, rfDrivers } from '../data';
import { useFeatureImportance, useModelMetrics } from '../hooks/useFageApi';

interface ModelInsightsViewProps {
  theme: SystemTheme;
}

export default function ModelInsightsView({ theme }: ModelInsightsViewProps) {
  const isDark = theme === 'sovereign';
  const [selectedModel, setSelectedModel] = useState<'xgb' | 'rf'>('xgb');
  const [activeTab, setActiveTab] = useState<'bar' | 'beeswarm'>('bar');

  const { data: metricsData } = useModelMetrics();
  const { data: importanceData } = useFeatureImportance(selectedModel === 'xgb' ? 'XGBoost' : 'RandomForest');

  const FEATURE_DESCRIPTIONS: Record<string, string> = {
    'F5': 'Velocity of Incoming Transfers (24h)',
    'F9': 'Ratio of External Transfers',
    'F11': 'Account Age in Days',
    'F24': 'Device IP Risk Score',
    'F26': 'Distance from Typical Location',
    'F40': 'Count of Linked/Associated Profiles',
    'F43': 'Cross-Border Transaction Ratio',
    'F46': 'Velocity Change Ratio (7d)',
    'F49': 'High-Risk Hosting ASN Match',
    'F52': 'Deposit Frequency Deviation',
    'F55': 'Night-time Transfer Ratio',
    'F60': 'Multiple Beneficiary Count',
    'F65': 'Layering Chain Length'
  };

  const getFriendlyFeatureName = (featureId: string) => {
    if (FEATURE_DESCRIPTIONS[featureId]) {
      return FEATURE_DESCRIPTIONS[featureId];
    }
    const match = [...shapDrivers, ...rfDrivers].find(d => d.featureId === featureId);
    return match ? match.name : `Anonymized Feature ${featureId}`;
  };

  const activeFeatures = React.useMemo(() => {
    if (importanceData && importanceData.importance_profile && importanceData.importance_profile.length > 0) {
      return importanceData.importance_profile.map((item) => {
        const match = [...shapDrivers, ...rfDrivers].find(d => d.featureId === item.feature);
        return {
          featureId: item.feature,
          name: match ? match.name : getFriendlyFeatureName(item.feature),
          type: match ? match.type : 'Model Feature',
          shapValue: match ? match.shapValue : item.mean_abs_attribution,
          importanceScore: item.mean_abs_attribution,
          value: match ? match.value : '0.00'
        };
      });
    }
    return selectedModel === 'xgb' ? shapDrivers : rfDrivers;
  }, [importanceData, selectedModel]);

  const modelName = selectedModel === 'xgb' ? 'XGBoost' : 'RandomForest';

  const aucScore = React.useMemo(() => {
    const modelKey = selectedModel === 'xgb' ? 'XGBoost' : 'RandomForest';
    if (metricsData && metricsData[modelKey]) {
      return metricsData[modelKey].roc_auc.toFixed(3);
    }
    return selectedModel === 'xgb' ? '0.942' : '0.925';
  }, [metricsData, selectedModel]);

  const aucChange = selectedModel === 'xgb' ? '+0.015' : '+0.008';

  const handleExportFeatures = () => {
    const headers = ['Feature ID', 'Feature Name', 'Importance Score'];
    const rows = activeFeatures.map(f => [
      f.featureId,
      f.name,
      f.importanceScore
    ]);
    const csvContent = "data:text/csv;charset=utf-8," 
      + [headers.join(','), ...rows.map(e => e.map(val => `"${val}"`).join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `FAGE_Feature_Importance_${modelName}_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
      {/* Header & Model Selector */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className={`text-2xl font-extrabold tracking-tight ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
            Model Insights
          </h2>
          <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-[#444653]'}`}>
            Analyze prediction drivers and feature importance for risk scoring models.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value as 'xgb' | 'rf')}
              className={`appearance-none font-sans text-xs px-3 py-2 pr-8 rounded-lg outline-none cursor-pointer border ${
                isDark 
                  ? 'bg-slate-900 border-slate-700 text-slate-300 focus:border-cyan-500' 
                  : 'bg-white border-[#c4c5d5] text-slate-700 focus:border-[#1e40af]'
              }`}
            >
              <option value="xgb">Model: XGB-Mule-V3.2</option>
              <option value="rf">Model: RF-Transfer-V2</option>
            </select>
            <Cpu size={13} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400" />
          </div>

          <button 
            onClick={handleExportFeatures}
            className={`flex items-center gap-2 px-4 py-2 border rounded-lg text-xs font-bold transition-all duration-300 h-9 ${
              isDark 
                ? 'bg-transparent border-slate-800 hover:bg-slate-800 text-slate-300' 
                : 'bg-white border-[#c4c5d5] text-slate-700 hover:bg-slate-100 shadow-sm'
            }`}
          >
            <Download size={14} />
            <span>Export</span>
          </button>
        </div>
      </div>

      {/* Bento Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Global Feature Importance Card (8 cols) */}
        <div className={`p-5 border rounded-xl lg:col-span-8 flex flex-col ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <div className="flex justify-between items-center mb-5 border-b border-slate-300 dark:border-slate-800 pb-2">
            <div>
              <h3 className={`text-sm font-bold tracking-tight ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                Global Feature Importance
              </h3>
              <span className="text-[10px] text-slate-400">Top influencing features across all predictions (Mean |SHAP|)</span>
            </div>
            
            <div className="flex items-center gap-3">
              <div className="flex border border-slate-305 dark:border-slate-800 rounded-lg overflow-hidden p-0.5 bg-slate-100 dark:bg-slate-950/60">
                <button
                  onClick={() => setActiveTab('bar')}
                  className={`px-3 py-1.5 text-[9px] font-bold rounded-md transition-all ${
                    activeTab === 'bar'
                      ? (isDark ? 'bg-cyan-500 text-[#051424]' : 'bg-[#1e40af] text-white')
                      : 'text-slate-450 hover:text-slate-200'
                  }`}
                >
                  Bar Chart
                </button>
                <button
                  onClick={() => setActiveTab('beeswarm')}
                  className={`px-3 py-1.5 text-[9px] font-bold rounded-md transition-all ${
                    activeTab === 'beeswarm'
                      ? (isDark ? 'bg-cyan-500 text-[#051424]' : 'bg-[#1e40af] text-white')
                      : 'text-slate-450 hover:text-slate-200'
                  }`}
                >
                  Beeswarm Plot
                </button>
              </div>
              <HelpCircle size={15} className="text-slate-400 cursor-pointer hover:text-indigo-400" title="Information on SHAP values" />
            </div>
          </div>

          {activeTab === 'bar' ? (
            /* Features horizontal listing */
            <div className="space-y-4 flex-1 flex flex-col justify-center">
             {activeFeatures.map((f) => {
                const scores = activeFeatures.map(x => x.importanceScore);
                const maxScore = scores.length > 0 ? Math.max(...scores) : 1.0;
                const percent = maxScore > 0 ? (f.importanceScore / maxScore) * 100 : 0;
                
                return (
                  <div key={f.featureId} className="flex items-center text-xs">
                    <span className="w-16 font-mono font-bold text-slate-400 dark:text-slate-500 pr-2 text-right">
                      {f.featureId}
                    </span>
                    
                    {/* Progress bar container */}
                    <div className="flex-1 h-6 bg-slate-100 dark:bg-slate-900/50 rounded-r overflow-hidden relative border border-transparent dark:border-slate-800/10">
                      <div 
                        className={`h-full rounded-r transition-all duration-500 flex items-center pl-3 ${
                          isDark ? 'bg-[#3755c3] shadow-[0_0_8px_rgba(55,85,195,0.4)]' : 'bg-gradient-to-r from-blue-700 to-[#1e40af]'
                        }`}
                        style={{ width: `${percent}%` }}
                      >
                        <span className="text-white text-[10px] font-bold">
                          {f.importanceScore.toFixed(3)}
                        </span>
                      </div>
                    </div>

                    <span className={`w-40 pl-3 font-medium truncate ${isDark ? 'text-slate-300' : 'text-slate-700'}`} title={f.name}>
                      {f.name}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            /* Beeswarm plot rendering */
            <div className="flex-1 flex flex-col items-center justify-center p-2 bg-slate-950/20 rounded-lg border border-dashed border-slate-300 dark:border-slate-800">
              {importanceData?.static_beeswarm_base64 ? (
                <img 
                  src={importanceData.static_beeswarm_base64} 
                  alt="SHAP Beeswarm Plot" 
                  className="max-h-[320px] w-full object-contain rounded-lg shadow-md"
                />
              ) : (
                <div className="text-xs text-slate-400 py-12 flex flex-col items-center gap-2">
                  <span className="animate-pulse">Loading static beeswarm attribution scatter coordinates...</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Global Summary Stats (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className={`p-4 border rounded-xl flex-1 justify-between flex flex-col ${
            isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
          }`}>
            <div>
              <p className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Model Accuracy (ROC AUC)</p>
              <div className="flex items-baseline gap-2 mt-2">
                <span className={`text-3xl font-extrabold ${isDark ? 'text-slate-200' : 'text-[#1a1b22]'}`}>
                  {aucScore}
                </span>
                <span className="text-[11px] font-bold text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded leading-none flex items-center">
                  <TrendingUp size={11} className="mr-0.5" />
                  {aucChange}
                </span>
              </div>
            </div>

            <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden mt-4">
              <div className={`h-full rounded-full ${isDark ? 'bg-cyan-500' : 'bg-[#1e40af]'}`} style={{ width: `${parseFloat(aucScore) * 100}%` }}></div>
            </div>
          </div>

          <div className={`p-4 border rounded-xl flex-1 ${
            isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
          }`}>
            <p className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Top Driver Shift (7d)</p>
            <p className={`text-xs mt-3 leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              Feature <span className="font-bold text-sky-600 dark:text-cyan-400">F3889</span> (Velocity of incoming transactions) has increased in importance by <span className="font-extrabold text-red-500">12%</span> over the last week. This correlates with a recent spike in coordinated digital transfer rings.
            </p>
          </div>
        </div>

        {/* Local waterfall explanation panel (Spans 12 cols) */}
        <div className={`border rounded-xl p-5 lg:col-span-12 ${
          isDark ? 'bg-slate-900/40 border-slate-800 text-slate-300' : 'bg-white border-[#c4c5d5] shadow-sm'
        }`}>
          <div className="flex justify-between items-center mb-5 border-b border-slate-300 dark:border-slate-800 pb-2">
            <div>
              <h3 className={`text-sm font-bold tracking-tight ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                Prediction Drivers (Local Explanation)
              </h3>
              <span className="text-[10px] text-slate-400">
                SHAP values for recent high-risk prediction ID: <span className="font-mono bg-slate-200 dark:bg-slate-800 px-1 rounded">PRD-8821-X</span>
              </span>
            </div>

            <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-bold bg-[#ffdad6] text-[#93000a] dark:bg-red-950/40 dark:text-red-300 border border-red-500/10">
              Risk Score: 92/100
            </span>
          </div>

          {/* Waterfall pseudo matrix */}
          <div className="overflow-x-auto w-full table-scroll">
            <table className="w-full text-left border-collapse text-xs whitespace-nowrap">
              <thead>
                <tr className={`border-b ${isDark ? 'bg-slate-900/30' : 'bg-slate-50'}`}>
                  <th className="p-3 font-bold text-slate-400 uppercase tracking-widest font-mono">Feature ID</th>
                  <th className="p-3 font-bold text-slate-400 uppercase tracking-widest font-mono">Feature Value</th>
                  <th className="p-3 font-bold text-slate-400 uppercase tracking-widest font-mono text-center">SHAP Value Impact (Base: 0.15)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-300/30 dark:divide-slate-850/60">
                {activeFeatures.slice(0, 5).map((f) => {
                  const isPositive = f.shapValue > 0;
                  const absVal = Math.min(Math.abs(f.shapValue) * 100, 100);
                  
                  return (
                    <tr key={f.featureId} className="hover:bg-slate-300/10 dark:hover:bg-slate-800/10 h-12">
                      <td className="p-3 font-bold">
                        <span className="text-slate-800 dark:text-slate-200 font-mono tracking-wide">{f.featureId}</span>
                        <span className="text-[10px] text-slate-400 font-medium block mt-0.5 font-sans">{f.name}</span>
                      </td>
                      <td className="p-3 font-extrabold font-mono text-slate-500 dark:text-slate-400">{f.value}</td>
                      <td className="p-3">
                        <div className="flex items-center w-full min-w-[240px]">
                          {/* Right bar for positive, left bar for negative impact */}
                          <div className="w-1/2 flex justify-end pr-1.5 border-r border-[#c4c5d5] dark:border-slate-850">
                            {!isPositive && (
                              <div 
                                className="h-4 bg-[#d3e4fe] border border-blue-500/10 text-[#0b1c30] text-[9px] font-bold flex items-center justify-end px-2.5 rounded-l-md leading-none"
                                style={{ width: `${absVal * 1.5}%` }}
                              >
                                {f.shapValue.toFixed(2)}
                              </div>
                            )}
                          </div>
                          
                          <div className="w-1/2 flex justify-start pl-1.5">
                            {isPositive && (
                              <div 
                                className="h-4 bg-[#ffdad6] border border-red-500/10 text-[#93000a] text-[9px] font-bold flex items-center justify-start px-2.5 rounded-r-md leading-none error-glow"
                                style={{ width: `${absVal * 1.5}%` }}
                              >
                                +{f.shapValue.toFixed(2)}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
