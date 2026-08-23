import React, { useEffect, useState } from 'react';
import { ShieldCheck, AlertTriangle, RefreshCw, X, AlertCircle } from 'lucide-react';
import { fageApi } from '../services/api';

interface BiasAuditModalProps {
  onClose: () => void;
}

export function BiasAuditModal({ onClose }: BiasAuditModalProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fageApi.getBiasAudit()
      .then(res => {
        setData(res);
        setLoading(false);
      })
      .catch(err => {
        setError(err?.response?.data?.detail || err.message || 'Failed to fetch bias audit');
        setLoading(false);
      });
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-surface-container w-full max-w-4xl rounded-2xl shadow-2xl border border-outline-variant overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-outline-variant bg-surface-container-low shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 text-primary rounded-lg">
              <ShieldCheck size={24} />
            </div>
            <div>
              <h2 className="text-xl font-black tracking-tight text-on-surface">Model Bias Audit</h2>
              <p className="text-xs text-on-surface-variant font-medium mt-0.5">Disparate impact analysis and fairness metrics</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-container-highest rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto custom-scrollbar flex-1 bg-surface-container">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-on-surface-variant">
              <div className="relative w-12 h-12 flex items-center justify-center mb-4">
                <div className="absolute inset-0 border-[3px] border-primary border-t-transparent rounded-full animate-spin"></div>
                <ShieldCheck size={20} className="text-primary animate-pulse" />
              </div>
              <p className="font-bold tracking-widest uppercase text-xs">Computing Disparate Impact...</p>
            </div>
          ) : error ? (
            <div className="p-6 bg-error/10 border border-error/20 rounded-xl flex items-start gap-4 text-error">
              <AlertTriangle size={24} className="shrink-0" />
              <div>
                <h3 className="font-bold text-sm mb-1">Audit Failed</h3>
                <p className="text-xs opacity-90">{error}</p>
              </div>
            </div>
          ) : data ? (
            <div className="space-y-8">
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {Object.entries(data.disparate_impact_ratios || {}).map(([group, ratio]: [string, any]) => {
                  const isUnfair = ratio < 0.8 || ratio > 1.25;
                  return (
                    <div key={group} className={`p-4 rounded-xl border ${isUnfair ? 'bg-error/5 border-error/20' : 'bg-surface-container-low border-outline-variant/30'}`}>
                      <div className="text-[10px] uppercase font-bold text-on-surface-variant tracking-widest mb-2">{group}</div>
                      <div className="flex items-baseline gap-2">
                        <span className={`text-2xl font-black ${isUnfair ? 'text-error' : 'text-on-surface'}`}>
                          {ratio.toFixed(2)}
                        </span>
                        <span className="text-xs font-medium text-on-surface-variant">ratio</span>
                      </div>
                      {isUnfair && (
                        <div className="mt-2 text-[10px] text-error font-bold flex items-center gap-1">
                          <AlertCircle size={10} /> Disparate Impact Detected
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div>
                <h3 className="text-sm font-black uppercase tracking-wider text-on-surface mb-4">Equal Opportunity Difference</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(data.equal_opportunity_difference || {}).map(([group, diff]: [string, any]) => {
                    const isHighDiff = Math.abs(diff) > 0.1;
                    return (
                      <div key={group} className="flex items-center justify-between p-3 rounded-lg bg-surface-container-low border border-outline-variant">
                        <span className="text-xs font-bold text-on-surface">{group}</span>
                        <span className={`text-sm font-mono font-black ${isHighDiff ? 'text-error' : 'text-primary'}`}>
                          {(diff * 100).toFixed(2)}%
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="p-4 bg-primary/10 border border-primary/20 rounded-xl flex items-start gap-4">
                 <ShieldCheck size={20} className="text-primary shrink-0 mt-0.5" />
                 <div>
                   <h3 className="text-xs font-bold text-primary uppercase tracking-wider mb-1">Compliance Status</h3>
                   <p className="text-sm text-on-surface">{data.compliance_status || 'System is operating within acceptable demographic parity limits.'}</p>
                 </div>
              </div>

            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
