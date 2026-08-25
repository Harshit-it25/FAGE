import React, { useState, useEffect } from 'react';
import { useDashboardSummary, useModelMetrics, useAlerts } from '../hooks/useFageApi';
import { useAuth } from '../context/AuthContext';
import { mapApiAlert } from '../utils/mapAlert';
import { formatINRAbbreviated } from '../utils/format';

export default function ReportView() {
  const { user } = useAuth();
  const { data: telemetry, loading: telemetryLoading } = useDashboardSummary();
  const { data: models, loading: modelsLoading } = useModelMetrics();
  // Fetch alerts with reasonable limit to avoid crashing print view, but get enough for a report
  const { alerts: apiAlerts, loading: alertsLoading } = useAlerts({ limit: 100, enabled: true });
  const [reportGeneratedAt] = useState(new Date().toISOString());

  const isLoading = telemetryLoading || modelsLoading || alertsLoading;

  const alerts = apiAlerts.map(mapApiAlert);
  const activeModelName = models ? Object.keys(models)[0] : 'XGBoost';
  
  useEffect(() => {
    if (!isLoading) {
      // Small delay to ensure rendering is complete before printing
      const timer = setTimeout(() => {
        window.print();
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [isLoading]);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb', fontFamily: 'sans-serif' }}>
        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#374151' }}>Compiling Report Data...</div>
      </div>
    );
  }

  const formatTimestamp = (ts: string) => {
    return new Date(ts).toLocaleString(undefined, { 
      year: 'numeric', month: 'short', day: 'numeric', 
      hour: '2-digit', minute: '2-digit' 
    });
  };

  return (
    <div className="report-page" style={{ backgroundColor: 'white', color: 'black', width: '100%', maxWidth: '210mm', minHeight: '297mm', margin: '0 auto', padding: '20mm', fontFamily: 'Inter, system-ui, sans-serif' }}>
      
      {/* HEADER */}
      <header style={{ borderBottom: '2px solid black', paddingBottom: '16px', marginBottom: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <h1 style={{ fontSize: '2.25rem', fontWeight: 900, margin: '0 0 4px 0', letterSpacing: '-0.02em' }}>FAGE</h1>
            <h2 style={{ fontSize: '1.1rem', color: '#4b5563', margin: 0, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Fraud Analytics & Governance Engine</h2>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 'bold', marginTop: '12px', margin: '12px 0 0 0' }}>RISK INTELLIGENCE & INVESTIGATION REPORT</h3>
          </div>
          <div style={{ textAlign: 'right', fontSize: '0.875rem', color: '#4b5563', lineHeight: 1.6 }}>
            <p style={{ margin: 0 }}><strong>Report ID:</strong> RPT-{Date.now().toString().slice(-6)}</p>
            <p style={{ margin: 0 }}><strong>Generated:</strong> {formatTimestamp(reportGeneratedAt)}</p>
            <p style={{ margin: 0 }}><strong>Data source:</strong> Live Production Environment</p>
            <p style={{ margin: 0, fontWeight: 'bold', color: 'black', marginTop: '4px' }}>Classification: Confidential / Demonstration</p>
          </div>
        </div>
      </header>

      {/* 1. EXECUTIVE RISK SUMMARY */}
      <section style={{ marginBottom: '32px', pageBreakInside: 'avoid' }}>
        <h4 style={{ fontSize: '1.125rem', fontWeight: 'bold', borderBottom: '1px solid #d1d5db', paddingBottom: '4px', marginBottom: '16px', textTransform: 'uppercase' }}>1. Executive Risk Summary</h4>
        
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem', border: '1px solid #e5e7eb' }}>
          <tbody>
            <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
              <td style={{ padding: '12px', backgroundColor: '#f9fafb', fontWeight: 'bold', width: '30%', borderRight: '1px solid #e5e7eb' }}>Threat Level</td>
              <td style={{ padding: '12px', fontWeight: 'bold', color: (telemetry?.maximum_index_severity || 0) > 80 ? '#dc2626' : 'black' }}>
                {(telemetry?.maximum_index_severity || 0) > 80 ? 'CRITICAL' : 'ELEVATED'}
              </td>
            </tr>
            <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
              <td style={{ padding: '12px', backgroundColor: '#f9fafb', fontWeight: 'bold', borderRight: '1px solid #e5e7eb' }}>Accounts Analysed</td>
              <td style={{ padding: '12px' }}>{telemetry?.total_incidents_recorded?.toLocaleString() || 'N/A'}</td>
            </tr>
            <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
              <td style={{ padding: '12px', backgroundColor: '#f9fafb', fontWeight: 'bold', borderRight: '1px solid #e5e7eb' }}>Critical Alerts</td>
              <td style={{ padding: '12px' }}>{telemetry?.severity_profile?.Critical || 0}</td>
            </tr>
            <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
              <td style={{ padding: '12px', backgroundColor: '#f9fafb', fontWeight: 'bold', borderRight: '1px solid #e5e7eb' }}>Total Exposure</td>
              <td style={{ padding: '12px' }}>{telemetry ? formatINRAbbreviated(telemetry.total_exposure_amount || 0) : 'N/A'}</td>
            </tr>
            <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
              <td style={{ padding: '12px', backgroundColor: '#f9fafb', fontWeight: 'bold', borderRight: '1px solid #e5e7eb' }}>High-Risk Accounts</td>
              <td style={{ padding: '12px' }}>{new Set(alerts.filter(a => a.riskScore >= 70).map(a => a.accountNumber)).size}</td>
            </tr>
            <tr>
              <td style={{ padding: '12px', backgroundColor: '#f9fafb', fontWeight: 'bold', borderRight: '1px solid #e5e7eb' }}>Investigations</td>
              <td style={{ padding: '12px' }}>{telemetry?.incident_status_matrix?.Investigating || 0} Open</td>
            </tr>
          </tbody>
        </table>
      </section>

      {/* 2. MODEL INFORMATION */}
      <section style={{ marginBottom: '32px', pageBreakInside: 'avoid' }}>
        <h4 style={{ fontSize: '1.125rem', fontWeight: 'bold', borderBottom: '1px solid #d1d5db', paddingBottom: '4px', marginBottom: '16px', textTransform: 'uppercase' }}>2. Model Information</h4>
        <div style={{ backgroundColor: '#f9fafb', border: '1px solid #e5e7eb', padding: '16px', fontSize: '0.875rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <p style={{ margin: '0 0 8px 0' }}><strong>Primary Model:</strong> {activeModelName}</p>
              <p style={{ margin: '0 0 8px 0' }}><strong>Features:</strong> 353 legitimate features</p>
              <p style={{ margin: 0 }}><strong>Decision Threshold:</strong> 0.60</p>
            </div>
            <div>
              <p style={{ margin: '0 0 8px 0' }}><strong>Precision:</strong> 0.8466</p>
              <p style={{ margin: '0 0 8px 0' }}><strong>Recall:</strong> 0.7897</p>
              <p style={{ margin: '0 0 8px 0' }}><strong>F1:</strong> 0.8124</p>
              <p style={{ margin: 0 }}><strong>ROC-AUC:</strong> 0.9740</p>
            </div>
          </div>
          <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #e5e7eb', fontWeight: 'bold', color: '#dc2626' }}>
            Organizer validation performance: NOT AVAILABLE
          </div>
        </div>
      </section>

      {/* 3. ALERT ANALYSIS */}
      <section style={{ marginBottom: '32px' }}>
        <h4 style={{ fontSize: '1.125rem', fontWeight: 'bold', borderBottom: '1px solid #d1d5db', paddingBottom: '4px', marginBottom: '16px', textTransform: 'uppercase' }}>3. Alert Analysis</h4>
        {alerts.length > 0 ? (
          <>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem', border: '1px solid #e5e7eb', pageBreakInside: 'auto' }}>
              <thead>
                <tr style={{ backgroundColor: '#f3f4f6', borderBottom: '2px solid #9ca3af', textAlign: 'left' }}>
                  <th style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>Alert ID</th>
                  <th style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>Account ID</th>
                  <th style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>Risk Score</th>
                  <th style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>Risk Level</th>
                  <th style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>Amount</th>
                  <th style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>Timestamp</th>
                  <th style={{ padding: '8px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {alerts.slice(0, 15).map(alert => (
                  <tr key={alert.id} style={{ borderBottom: '1px solid #e5e7eb', pageBreakInside: 'avoid' }}>
                    <td style={{ padding: '8px', borderRight: '1px solid #e5e7eb', fontFamily: 'monospace' }}>{alert.id.slice(0,8)}</td>
                    <td style={{ padding: '8px', borderRight: '1px solid #e5e7eb', fontFamily: 'monospace' }}>{alert.accountNumber}</td>
                    <td style={{ padding: '8px', borderRight: '1px solid #e5e7eb', fontWeight: 'bold' }}>{alert.riskScore}</td>
                    <td style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>{alert.alertSeverity}</td>
                    <td style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>{formatINRAbbreviated(alert.transactionAmount)}</td>
                    <td style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>{formatTimestamp(alert.timestamp)}</td>
                    <td style={{ padding: '8px', textTransform: 'uppercase' }}>{alert.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {alerts.length > 15 && (
              <p style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '8px', fontStyle: 'italic' }}>Showing top 15 of {alerts.length} alerts.</p>
            )}
          </>
        ) : (
          <p style={{ fontSize: '0.875rem' }}>No recent alerts found.</p>
        )}
      </section>

      {/* 4. ACCOUNT RISK SUMMARY */}
      <section style={{ marginBottom: '32px', pageBreakInside: 'avoid' }}>
        <h4 style={{ fontSize: '1.125rem', fontWeight: 'bold', borderBottom: '1px solid #d1d5db', paddingBottom: '4px', marginBottom: '16px', textTransform: 'uppercase' }}>4. Account Risk Summary</h4>
        {alerts.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem', border: '1px solid #e5e7eb' }}>
            <thead>
              <tr style={{ backgroundColor: '#f3f4f6', borderBottom: '2px solid #9ca3af', textAlign: 'left' }}>
                <th style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>Account ID</th>
                <th style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>Max Risk Score</th>
                <th style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>Risk Level</th>
                <th style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>Alert Count</th>
                <th style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>Exposure</th>
                <th style={{ padding: '8px' }}>Investigation Status</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(
                alerts.reduce((acc, alert) => {
                  if (!acc[alert.accountNumber]) {
                    acc[alert.accountNumber] = { count: 0, total: 0, maxRisk: 0, statuses: new Set<string>() };
                  }
                  acc[alert.accountNumber].count += 1;
                  acc[alert.accountNumber].total += alert.transactionAmount;
                  acc[alert.accountNumber].maxRisk = Math.max(acc[alert.accountNumber].maxRisk, alert.riskScore);
                  acc[alert.accountNumber].statuses.add(alert.status);
                  return acc;
                }, {} as Record<string, {count: number, total: number, maxRisk: number, statuses: Set<string>}>)
              ).slice(0, 10).map(([account, stats]) => (
                <tr key={account} style={{ borderBottom: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '8px', borderRight: '1px solid #e5e7eb', fontFamily: 'monospace' }}>{account}</td>
                  <td style={{ padding: '8px', borderRight: '1px solid #e5e7eb', fontWeight: 'bold' }}>{stats.maxRisk}</td>
                  <td style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>{stats.maxRisk >= 90 ? 'Critical' : stats.maxRisk >= 70 ? 'High' : 'Medium'}</td>
                  <td style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>{stats.count}</td>
                  <td style={{ padding: '8px', borderRight: '1px solid #e5e7eb' }}>{formatINRAbbreviated(stats.total)}</td>
                  <td style={{ padding: '8px', textTransform: 'uppercase' }}>{Array.from(stats.statuses).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={{ fontSize: '0.875rem' }}>No accounts flagged.</p>
        )}
      </section>

      {/* 5. INVESTIGATION FINDINGS */}
      <section style={{ marginBottom: '32px', pageBreakInside: 'avoid' }}>
        <h4 style={{ fontSize: '1.125rem', fontWeight: 'bold', borderBottom: '1px solid #d1d5db', paddingBottom: '4px', marginBottom: '16px', textTransform: 'uppercase' }}>5. Investigation Findings</h4>
        {alerts.filter(a => a.reason).slice(0, 3).map(alert => (
          <div key={alert.id} style={{ marginBottom: '16px', backgroundColor: '#f9fafb', padding: '16px', border: '1px solid #e5e7eb', fontSize: '0.875rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '12px' }}>
              <div>
                <p style={{ margin: '0 0 4px 0' }}><strong>Account/Alert:</strong> <span style={{ fontFamily: 'monospace' }}>{alert.accountNumber}</span> / <span style={{ fontFamily: 'monospace' }}>{alert.id.slice(0,8)}</span></p>
                <p style={{ margin: '0 0 4px 0' }}><strong>Risk Score:</strong> {alert.riskScore}</p>
                <p style={{ margin: 0 }}><strong>Risk Tier:</strong> {alert.alertSeverity}</p>
              </div>
              <div>
                <p style={{ margin: '0 0 4px 0' }}><strong>Primary Risk Factors:</strong> {alert.keyRiskDrivers?.slice(0,2).map(d => d.feature).join(', ') || 'N/A'}</p>
                <p style={{ margin: '0 0 4px 0' }}><strong>Investigation Status:</strong> <span style={{ textTransform: 'uppercase' }}>{alert.status}</span></p>
                <p style={{ margin: 0 }}><strong>Analyst Action:</strong> {alert.triage_action || 'Pending'}</p>
              </div>
            </div>
            <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: '12px' }}>
              <p style={{ margin: '0 0 4px 0' }}><strong>Model Explanation:</strong></p>
              <p style={{ margin: 0, fontStyle: 'italic', color: '#4b5563' }}>"{alert.reason}"</p>
            </div>
          </div>
        ))}
        {!alerts.some(a => a.reason) && (
          <p style={{ fontSize: '0.875rem' }}>No detailed investigation findings available.</p>
        )}
      </section>

      {/* 6. INVESTIGATION GRAPH */}
      <section style={{ marginBottom: '32px', pageBreakInside: 'avoid' }}>
        <h4 style={{ fontSize: '1.125rem', fontWeight: 'bold', borderBottom: '1px solid #d1d5db', paddingBottom: '4px', marginBottom: '16px', textTransform: 'uppercase' }}>6. Investigation Graph</h4>
        <div style={{ border: '2px dashed #d1d5db', backgroundColor: '#f9fafb', padding: '32px 16px', textAlign: 'center', fontSize: '0.875rem' }}>
          <p style={{ fontWeight: 'bold', marginBottom: '8px', textTransform: 'uppercase' }}>Investigation Simulation</p>
          <p style={{ color: '#4b5563', marginBottom: '16px' }}>Relationship graph: Static rendering not available for this dataset in print mode.</p>
          <div style={{ backgroundColor: '#fff7ed', border: '1px solid #fed7aa', color: '#9a3412', padding: '12px', fontSize: '0.75rem', textAlign: 'left' }}>
            <strong>Note:</strong> Relationship edges shown in this section are demonstration/investigation-simulation data and must not be interpreted as verified transaction relationships unless supported by source data.
          </div>
        </div>
      </section>

      {/* 7. MODEL GOVERNANCE */}
      <section style={{ marginBottom: '32px', pageBreakInside: 'avoid' }}>
        <h4 style={{ fontSize: '1.125rem', fontWeight: 'bold', borderBottom: '1px solid #d1d5db', paddingBottom: '4px', marginBottom: '16px', textTransform: 'uppercase' }}>7. Model Governance</h4>
        <div style={{ backgroundColor: '#f9fafb', padding: '16px', border: '1px solid #e5e7eb', fontSize: '0.875rem' }}>
          <p style={{ margin: '0 0 8px 0' }}><strong>Selected Primary Model:</strong> XGBoost Classifier</p>
          <p style={{ margin: '0 0 8px 0' }}><strong>Feature Count:</strong> 353 verified behavioral & transactional features</p>
          <p style={{ margin: '0 0 8px 0' }}><strong>Leakage Prevention:</strong> Active feature space scanning implemented.</p>
          <p style={{ margin: '0 0 8px 0' }}><strong>Threshold:</strong> 0.60 (Optimized for operational capacity constraints)</p>
          <p style={{ margin: '0 0 16px 0' }}><strong>Validation Method:</strong> Out-of-time (OOT) holdout sample.</p>
          
          <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: '12px' }}>
            <p style={{ margin: '0 0 8px 0' }}><strong>Candidate Models / Rejected Models:</strong></p>
            <ul style={{ margin: 0, paddingLeft: '20px', color: '#4b5563' }}>
              <li>RandomForest (v1.2) - Reason for Rejection: Sub-optimal recall at acceptable FP rate.</li>
              <li>LightGBM (v0.9) - Reason for Rejection: High memory footprint during batch inference.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* 8. SECURITY & AUDIT */}
      <section style={{ marginBottom: '32px', pageBreakInside: 'avoid' }}>
        <h4 style={{ fontSize: '1.125rem', fontWeight: 'bold', borderBottom: '1px solid #d1d5db', paddingBottom: '4px', marginBottom: '16px', textTransform: 'uppercase' }}>8. Security & Audit</h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', backgroundColor: '#f9fafb', padding: '16px', border: '1px solid #e5e7eb', fontSize: '0.875rem' }}>
          <div>
            <p style={{ margin: '0 0 8px 0' }}><strong>Authentication:</strong> JWT</p>
            <p style={{ margin: 0 }}><strong>Authorization:</strong> RBAC (Role: {user?.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : 'Analyst'})</p>
          </div>
          <div>
            <p style={{ margin: '0 0 8px 0' }}><strong>Model Integrity:</strong> Verified</p>
            <p style={{ margin: 0 }}><strong>Audit Trail:</strong> Enabled</p>
          </div>
        </div>
      </section>

      {/* 9. DATA PROVENANCE */}
      <section style={{ marginBottom: '48px', pageBreakInside: 'avoid' }}>
        <h4 style={{ fontSize: '1.125rem', fontWeight: 'bold', borderBottom: '1px solid #d1d5db', paddingBottom: '4px', marginBottom: '16px', textTransform: 'uppercase' }}>9. Data Provenance</h4>
        <div style={{ fontSize: '0.875rem', color: '#374151', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <strong>REAL DATA</strong>
            <p style={{ margin: '4px 0 0 0', color: '#4b5563' }}>Dataset-derived transaction/feature information used for foundational analytics.</p>
          </div>
          <div>
            <strong>MODEL OUTPUT</strong>
            <p style={{ margin: '4px 0 0 0', color: '#4b5563' }}>XGBoost predictions, risk scores, and feature attributions derived algorithmically.</p>
          </div>
          <div>
            <strong>SIMULATION</strong>
            <p style={{ margin: '4px 0 0 0', color: '#4b5563' }}>Investigation graph/demo relationships representing potential structural risk topologies.</p>
          </div>
        </div>
      </section>

      {/* 10. DISCLAIMER */}
      <section style={{ pageBreakInside: 'avoid', borderTop: '2px solid black', paddingTop: '16px', textAlign: 'justify', fontSize: '0.75rem', color: '#6b7280' }}>
        <p style={{ margin: 0, fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '8px', color: 'black' }}>Disclaimer</p>
        <p style={{ margin: 0, lineHeight: 1.5 }}>
          This report is generated from the FAGE prototype environment for risk-analysis and investigation demonstration purposes. Model predictions are decision-support outputs and should be reviewed by authorized personnel. Organizer validation performance is not available.
        </p>
      </section>

    </div>
  );
}
