import React, { useState, useEffect, useMemo } from 'react';
import { ViewMode, SystemTheme, Alert, AnalystNote, DataSourceType } from './types';
import { shapDrivers } from './data';

import Sidebar from './components/Sidebar';
import DashboardView from './components/DashboardView';
import InvestigationWorkbenchView from './components/InvestigationWorkbenchView';
import RiskExplorerView from './components/RiskExplorerView';
import ModelInsightsView from './components/ModelInsightsView';
import FraudInsightsView from './components/FraudInsightsView';
import ModelPerformanceView from './components/ModelPerformanceView';
import AlertsQueueView from './components/AlertsQueueView';

import { useAlerts, useUpdateAlert } from './hooks/useFageApi';

export default function App() {
  const [currentView, setView] = useState<ViewMode>('dashboard');
  const [theme, setTheme] = useState<SystemTheme>('analytics');
  
  // Local state container for reactive backup and instant updates
  const [localAlerts, setLocalAlerts] = useState<Alert[]>([]);
  const [activeAlertId, setActiveAlertId] = useState<string>('');
  const [localNotes, setLocalNotes] = useState<Record<string, AnalystNote[]>>({});

  // Initialize Backend synchronization hooks
  const { alerts: apiAlerts, error: apiError, refetch: refetchAlerts } = useAlerts();
  const { updateAlert } = useUpdateAlert();

  const [dataSource, setDataSource] = useState<DataSourceType>('live-all');
  const [hasSetDefault, setHasSetDefault] = useState(false);

  const isBackendOnline = useMemo(() => {
    return !apiError && apiAlerts && apiAlerts.length > 0;
  }, [apiAlerts, apiError]);

  useEffect(() => {
    if (isBackendOnline && !hasSetDefault) {
      setDataSource('live-all');
      setHasSetDefault(true);
    }
  }, [isBackendOnline, hasSetDefault]);

  // Combine and map apiAlerts if present, falling back to localState
  const processedAlerts = useMemo(() => {
    const hasBackendData = apiAlerts && apiAlerts.length > 0;
    
    if ((dataSource === 'live-all' || dataSource === 'live-target' || dataSource === 'live-dataset') && hasBackendData) {
      const mapped = apiAlerts.map(a => {
        const risk_score = a.risk_score || 0;
        const confidencePercent = Math.round(50 + (risk_score / 2.0));
        
        let customType = 'Rapid Fund Transfer (Mule)';
        if (a.id.startsWith('ALT-TGT-') || risk_score >= 50) {
          customType = 'Mule Account';
        } else if (a.reason) {
          if (a.reason.includes('Dataset Target Fraud Account')) {
            customType = 'Mule Account';
          } else if (a.reason.includes('Low Risk Dataset Account')) {
            customType = 'Normal Account Profile';
          } else if (a.reason.includes('triggered')) {
            customType = a.reason.split('triggered')[0]?.trim() || 'Policy Trigger Exception';
          } else {
            const dotIndex = a.reason.indexOf('.');
            const firstClause = dotIndex !== -1 ? a.reason.substring(0, dotIndex) : a.reason;
            customType = firstClause.length > 35 ? firstClause.substring(0, 35) + '...' : firstClause;
          }
        }

        const customPrio = a.severity === 'Critical' ? 'P1 - Immediate' : a.severity === 'High' ? 'P2 - Review' : 'P3 - Monitor';
        const timestampVal = a.timestamp ? (a.timestamp.includes('T') ? 'Just now' : a.timestamp) : 'Recent';
        const amount = a.amount || 0;
        
        return {
          id: a.id,
          accountNumber: a.sender_id || 'ACC-8839',
          type: customType,
          reason: a.reason,
          riskScore: risk_score,
          confidence: `${risk_score >= 80 ? 'High' : risk_score >= 60 ? 'Medium' : 'Low'} (${confidencePercent}%)`,
          confidenceVal: confidencePercent,
          status: (a.status || 'Open') as any,
          timestamp: timestampVal,
          holderName: a.receiver_id ? `Beneficiary: ${a.receiver_id}` : 'Robert P. Jenkins',
          ssn: '***-**-3942',
          dateOpened: '2023-10-14',
          balance: amount,
          ytdInflows: amount * 1.2,
          ytdOutflows: amount,
          prio: customPrio,
          assignedTo: a.assigned_to || 'Unassigned',
          logs: a.logs
        };
      });

      if (dataSource === 'live-target') {
        return mapped.filter(a => a.id.startsWith('ALT-TGT-') || a.type === 'Mule Account');
      }
      if (dataSource === 'live-dataset') {
        return mapped.filter(a => a.id.startsWith('ALT-DS-'));
      }
      return mapped;
    }
    return localAlerts;
  }, [apiAlerts, localAlerts, dataSource]);

  // Synchronize document colors for seamless view transition
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'sovereign') {
      root.classList.add('dark');
      document.body.style.backgroundColor = '#051224';
    } else {
      root.classList.remove('dark');
      document.body.style.backgroundColor = '#fbf8ff';
    }
  }, [theme]);

  // Handle case eye visibility click across boards
  const handleSelectAlert = (id: string) => {
    setActiveAlertId(id);
    setView('investigation');
  };

  // State transaction modification handlers (Updating status)
  const handleUpdateStatus = async (id: string, status: 'Open' | 'Escalated' | 'Closed' | 'Investigating') => {
    // 1. Update local reactive state instantly for snappy UI transitions
    setLocalAlerts((prevAlerts) =>
      prevAlerts.map((a) => (a.id === id ? { ...a, status } : a))
    );
    
    // 2. Persist to backend database via REST PUT endpoint
    try {
      await updateAlert(id, { status: status as any });
      if (refetchAlerts) refetchAlerts();
    } catch (err) {
      console.error('Failed to sync status update with FastAPI:', err);
    }
  };

  // State assignment modification handler (Updating assignee)
  const handleUpdateAssignment = async (id: string, assignee: string) => {
    setLocalAlerts((prevAlerts) =>
      prevAlerts.map((a) => (a.id === id ? { ...a, assignedTo: assignee } : a))
    );

    try {
      const activeStatus = processedAlerts.find(a => a.id === id)?.status || 'Open';
      await updateAlert(id, { status: activeStatus as any, assigned_to: assignee });
      if (refetchAlerts) refetchAlerts();
    } catch (err) {
      console.error('Failed to sync assignment update with FastAPI:', err);
    }
  };

  // State note appending modification handlers (Saving Note)
  const handleAddNote = async (id: string, noteText: string) => {
    const freshNote: AnalystNote = {
      id: `AN-${Date.now()}`,
      author: 'Admin (Operator)',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' UTC',
      content: noteText,
      isSystem: false,
    };

    setLocalNotes((prevNotes) => {
      const existing = prevNotes[id] || [];
      return {
        ...prevNotes,
        [id]: [...existing, freshNote],
      };
    });

    // Persist as a note entry onto alert audit trail logs
    try {
      const activeStatus = processedAlerts.find(a => a.id === id)?.status || 'Open';
      await updateAlert(id, { status: activeStatus as any, notes: noteText });
      if (refetchAlerts) refetchAlerts();
    } catch (err) {
      console.error('Failed to append analyst note in FastAPI:', err);
    }
  };

  const activeAlert = processedAlerts.find((a) => a.id === activeAlertId) || processedAlerts[0];

  const renderView = () => {
    switch (currentView) {
      case 'dashboard':
        return (
          <DashboardView 
            alerts={processedAlerts} 
            onSelectAlert={handleSelectAlert} 
            theme={theme} 
            onRefreshAlerts={refetchAlerts}
            dataSource={dataSource}
            setDataSource={setDataSource}
            isBackendOnline={isBackendOnline}
            apiAlertsCount={apiAlerts ? apiAlerts.length : 0}
            apiTargetCount={apiAlerts ? apiAlerts.filter(a => a.id.startsWith('ALT-TGT-') || (a.risk_score !== undefined && a.risk_score >= 50)).length : 0}
            apiDatasetCount={apiAlerts ? apiAlerts.filter(a => a.id.startsWith('ALT-DS-')).length : 0}
            apiError={apiError}
          />
        );
      case 'investigation':
        if (!activeAlert) {
          return (
            <div className={`p-8 border rounded-xl text-center space-y-4 ${
              theme === 'sovereign' ? 'bg-slate-900/40 border-slate-800 text-slate-400' : 'bg-white border-[#c4c5d5] text-slate-650 shadow-sm'
            }`}>
              <h3 className="text-lg font-bold">No Active Case Selected</h3>
              <p className="text-xs">Please select an alert from the Dashboard or Alerts Queue to inspect it.</p>
              <button 
                onClick={() => setView('dashboard')}
                className={`px-4 py-2 text-xs font-bold rounded-lg transition-all duration-300 ${
                  theme === 'sovereign' ? 'bg-cyan-500 hover:bg-cyan-600 text-[#051424] cyan-glow' : 'bg-[#1e40af] hover:bg-opacity-95 text-white'
                }`}
              >
                Go to Dashboard
              </button>
            </div>
          );
        }
        return (
          <InvestigationWorkbenchView
            activeAlert={activeAlert}
            drivers={shapDrivers}
            notes={localNotes}
            onAddNote={handleAddNote}
            onUpdateStatus={handleUpdateStatus}
            onUpdateAssignment={handleUpdateAssignment}
            theme={theme}
            alerts={processedAlerts}
            onSelectAlert={handleSelectAlert}
          />
        );
      case 'explorer':
        return (
          <RiskExplorerView 
            alerts={processedAlerts} 
            onSelectAlert={handleSelectAlert} 
            theme={theme} 
          />
        );
      case 'insights':
        return <ModelInsightsView theme={theme} />;
      case 'fraud':
        return (
          <FraudInsightsView 
            alerts={processedAlerts} 
            onSelectAlert={handleSelectAlert} 
            theme={theme} 
          />
        );
      case 'performance':
        return <ModelPerformanceView theme={theme} />;
      case 'alerts':
        return (
          <AlertsQueueView
            alerts={processedAlerts}
            onSelectAlert={handleSelectAlert}
            onUpdateStatus={handleUpdateStatus}
            theme={theme}
          />
        );
    }
  };

  const mainContainerClass = theme === 'sovereign'
    ? 'bg-[#050e1c] text-slate-300'
    : 'bg-[#faf9ff] text-slate-800';

  return (
    <div className={`flex flex-col md:flex-row h-screen min-w-full overflow-hidden ${mainContainerClass} font-sans`}>
      <Sidebar 
        currentView={currentView} 
        setView={setView} 
        theme={theme} 
        toggleTheme={() => setTheme(theme === 'analytics' ? 'sovereign' : 'analytics')} 
        openAlertsCount={processedAlerts.filter(a => a.status === 'Open').length}
        dataSource={dataSource}
        setDataSource={setDataSource}
        isBackendOnline={isBackendOnline}
        apiAlertsCount={apiAlerts ? apiAlerts.length : 0}
        apiTargetCount={apiAlerts ? apiAlerts.filter(a => a.id.startsWith('ALT-TGT-') || (a.risk_score !== undefined && a.risk_score >= 50)).length : 0}
        apiDatasetCount={apiAlerts ? apiAlerts.filter(a => a.id.startsWith('ALT-DS-')).length : 0}
      />

      {/* Main Content Layout */}
      <main className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6">
        <div className="max-w-7xl mx-auto xl:px-4">
          {renderView()}
        </div>
      </main>
    </div>
  );
}
