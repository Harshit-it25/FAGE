import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Routes, Route, Navigate, useNavigate, useParams, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { SystemTheme, Alert, AnalystNote, DataSourceType } from './types';
import { Search, Bell, HelpCircle, AlertTriangle, X } from 'lucide-react';

import Sidebar from './components/Sidebar';
import DashboardView from './components/DashboardView';
import InvestigationWorkbenchView from './components/InvestigationWorkbenchView';
import RiskExplorerView from './components/RiskExplorerView';


import AlertsQueueView from './components/AlertsQueueView';
import LoginView from './components/LoginView';
import AdminAuditView from './components/AdminAuditView';
import DifferentialPrivacyControls from './components/DifferentialPrivacyControls';

import { useDashboardSummary, useUpdateAlert, useAlertById, useAlerts } from './hooks/useFageApi';
import { mapApiAlert } from './utils/mapAlert';
import { useAuth } from './context/AuthContext';

const VIEW_PATHS = ['dashboard', 'investigation', 'explorer', 'alerts', 'admin', 'dp-ledger'] as const;
type ViewPath = (typeof VIEW_PATHS)[number];

function pathToView(pathname: string): ViewPath {
  const seg = pathname.split('/').filter(Boolean)[0] || 'dashboard';
  return (VIEW_PATHS as readonly string[]).includes(seg) ? (seg as ViewPath) : 'dashboard';
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode; onReset: () => void }, { hasError: boolean; error: Error | null }> {
  declare state: { hasError: boolean; error: Error | null };
  declare props: { children: React.ReactNode; onReset: () => void };
  constructor(props: { children: React.ReactNode; onReset: () => void }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("View crashed:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-on-surface gap-4">
          <AlertTriangle size={48} className="text-error" />
          <div className="text-center max-w-md">
            <h2 className="text-xl font-bold mb-2">View Render Exception</h2>
            <p className="text-sm text-on-surface-variant mb-4">An unexpected error occurred while rendering this interface. Our fallback UI has prevented the dashboard from going blank.</p>
            <pre className="text-xs font-mono bg-surface-container p-3 rounded text-error text-left overflow-auto max-h-32 mb-4">
              {this.state.error?.message || 'Unknown render error'}
            </pre>
          </div>
          <button
            onClick={() => {
              (this as React.Component<{ children: React.ReactNode; onReset: () => void }, { hasError: boolean; error: Error | null }>).setState({ hasError: false, error: null });
              this.props.onReset();
            }}
            className="px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-sm hover:opacity-90 transition-opacity"
          >
            Reset to Alerts Queue
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function WorkbenchShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { alertId: routeAlertId } = useParams<{ alertId?: string }>();

  const [theme, setTheme] = useState<SystemTheme>(() =>
    (localStorage.getItem('fage_theme') as SystemTheme) || 'analytics'
  );
  const [localNotes, setLocalNotes] = useState<Record<string, AnalystNote[]>>({});
  const [globalSearch, setGlobalSearch] = useState('');
  const [optimisticStatus, setOptimisticStatus] = useState<Record<string, Alert['status']>>({});
  const [showHelp, setShowHelp] = useState(false);
  const [alertsRefreshKey, setAlertsRefreshKey] = useState(0);
  const [searchDebounce, setSearchDebounce] = useState('');

  const [dataSource, setDataSource] = useState<DataSourceType>('live-all');
  const [hasSetDefault, setHasSetDefault] = useState(false);

  const currentView = pathToView(location.pathname);
  const activeAlertId = routeAlertId || '';

  const { data: dashboardData, error: apiError, loading: dashboardLoading, refetch: refetchDashboard } = useDashboardSummary();
  const { updateAlert } = useUpdateAlert();
  const { alert: fetchedAlert, loading: alertLoading, refetch: refetchActiveAlert } = useAlertById(activeAlertId || undefined);

  const isBackendOnline = !apiError && dashboardData !== null;

  useEffect(() => {
    const timer = setTimeout(() => setSearchDebounce(globalSearch.trim()), 300);
    return () => clearTimeout(timer);
  }, [globalSearch]);

  const { alerts: searchApiAlerts } = useAlerts({
    search: searchDebounce || undefined,
    limit: 8,
    enabled: isBackendOnline && searchDebounce.length > 0,
  });

  const bumpAlertsRefresh = useCallback(() => {
    setAlertsRefreshKey(k => k + 1);
    refetchDashboard(false);
    if (activeAlertId) refetchActiveAlert();
  }, [refetchDashboard, refetchActiveAlert, activeAlertId]);

  useEffect(() => {
    localStorage.setItem('fage_theme', theme);
  }, [theme]);

  useEffect(() => {
    if (isBackendOnline && !hasSetDefault) {
      setDataSource('live-all');
      setHasSetDefault(true);
    }
  }, [isBackendOnline, hasSetDefault]);

  const setView = useCallback(
    (view: ViewPath | string) => {
      if (view === 'investigation' && activeAlertId) {
        navigate(`/investigation/${activeAlertId}`);
      } else if (view === 'investigation') {
        navigate('/investigation');
      } else {
        navigate(`/${view}`);
      }
    },
    [navigate, activeAlertId]
  );

  const activeAlert = useMemo(() => {
    if (!fetchedAlert) return undefined;
    const mapped = mapApiAlert(fetchedAlert);
    return {
      ...mapped,
      status: optimisticStatus[mapped.id] ?? mapped.status,
    };
  }, [fetchedAlert, optimisticStatus]);

  const searchResults = useMemo(() => {
    if (!searchDebounce) return [];
    return searchApiAlerts.map(mapApiAlert);
  }, [searchApiAlerts, searchDebounce]);

  const handleSelectAlert = useCallback(
    (id: string) => {
      setGlobalSearch('');
      navigate(`/investigation/${encodeURIComponent(id)}`);
    },
    [navigate]
  );

  const handleUpdateStatus = async (id: string, status: Alert['status']) => {
    setOptimisticStatus(prev => ({ ...prev, [id]: status }));
    try {
      await updateAlert(id, { status, operator_name: user?.display_name });
      bumpAlertsRefresh();
      setOptimisticStatus(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (err) {
      setOptimisticStatus(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      console.error('Failed to sync status update with FastAPI:', err);
    }
  };

  const handleUpdateAssignment = async (id: string, assignee: string) => {
    try {
      await updateAlert(id, {
        assigned_to: assignee,
        operator_name: user?.display_name,
      });
      bumpAlertsRefresh();
    } catch (err) {
      console.error('Failed to sync assignment update with FastAPI:', err);
    }
  };

  const handleBulkStatus = async (ids: string[], status: Alert['status']) => {
    const newOptimistic: Record<string, Alert['status']> = {};
    ids.forEach(id => { newOptimistic[id] = status; });
    setOptimisticStatus(prev => ({ ...prev, ...newOptimistic }));
    
    try {
      const results = await Promise.allSettled(
        ids.map(id => updateAlert(id, { status, operator_name: user?.display_name }))
      );
      const failedIds = new Set(
        ids.filter((_, i) => results[i].status === 'rejected')
      );
      if (failedIds.size > 0) {
        console.error(`Bulk status update: ${failedIds.size} of ${ids.length} failed.`);
      }
      bumpAlertsRefresh();
      
      setOptimisticStatus(prev => {
        const next = { ...prev };
        ids.forEach(id => delete next[id]);
        return next;
      });
    } catch (err) {
      console.error('Failed to sync bulk update:', err);
      
      setOptimisticStatus(prev => {
        const next = { ...prev };
        ids.forEach(id => delete next[id]);
        return next;
      });
    }
  };

  const handleAddNote = async (id: string, noteText: string) => {
    const freshNote: AnalystNote = {
      id: `AN-${Date.now()}`,
      author: user?.display_name || 'Operator',
      timestamp: new Date().toISOString(),
      content: noteText,
      isSystem: false,
    };
    setLocalNotes(prevNotes => ({ ...prevNotes, [id]: [...(prevNotes[id] || []), freshNote] }));
    try {
      await updateAlert(id, {
        notes: noteText,
        operator_name: user?.display_name,
      });
      bumpAlertsRefresh();
    } catch (err) {
      console.error('Failed to append analyst note in FastAPI:', err);
    }
  };

  const handleNewInvestigation = () => {
    navigate('/alerts');
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchResults.length > 0) handleSelectAlert(searchResults[0].id);
    if (e.key === 'Escape') setGlobalSearch('');
  };

  const openAlertsCount = dashboardData?.incident_status_matrix?.Open ?? 0;
  const totalAlertsCount = dashboardData?.total_incidents_recorded ?? 0;

  const renderView = () => {
    switch (currentView) {
      case 'dashboard':
        return (
          <DashboardView
            onSelectAlert={handleSelectAlert}
            theme={theme}
            onRefreshAlerts={bumpAlertsRefresh}
            dataSource={dataSource}
            setDataSource={setDataSource}
            isBackendOnline={isBackendOnline}
            alertsLoading={dashboardLoading}
            apiAlertsCount={totalAlertsCount}
            apiTargetCount={dashboardData?.mule_alert_count ?? 0}
            apiDatasetCount={dashboardData?.dataset_alert_count ?? 0}
            apiError={apiError}
            telemetry={dashboardData}
          />
        );
      case 'investigation':
        if (alertLoading && activeAlertId) {
          return (
            <div className="flex-1 flex flex-col items-center justify-center text-on-surface-variant gap-4 p-8">
              <p className="text-sm">Loading alert details...</p>
            </div>
          );
        }
        if (!activeAlert) {
          return (
            <div className="flex-1 flex flex-col items-center justify-center text-on-surface-variant gap-4 p-8">
              <AlertTriangle size={40} className="text-on-surface-variant/40" />
              <div className="text-center">
                <p className="text-lg font-bold text-on-surface mb-1">
                  {activeAlertId ? 'Alert not found in current data source' : 'No alert selected'}
                </p>
                <p className="text-sm">Pick an alert from the Alerts Queue or Dashboard to begin an investigation.</p>
              </div>
              <button
                onClick={() => navigate('/alerts')}
                className="px-4 py-2 bg-primary text-on-primary rounded-lg text-sm font-bold hover:opacity-90 transition-opacity"
              >
                Browse Alerts Queue
              </button>
            </div>
          );
        }
        return (
          <InvestigationWorkbenchView
            activeAlert={activeAlert}
            notes={localNotes}
            onAddNote={handleAddNote}
            onUpdateStatus={handleUpdateStatus}
            onUpdateAssignment={handleUpdateAssignment}
            theme={theme}
            dataSource={dataSource}
            isBackendOnline={isBackendOnline}
            onSelectAlert={handleSelectAlert}
          />
        );
      case 'explorer':
        return (
          <RiskExplorerView
            onSelectAlert={handleSelectAlert}
            theme={theme}
            dataSource={dataSource}
            isBackendOnline={isBackendOnline}
          />
        );

      case 'alerts':
        return (
          <AlertsQueueView
            onSelectAlert={handleSelectAlert}
            onUpdateStatus={handleUpdateStatus}
            onUpdateAssignment={handleUpdateAssignment}
            onBulkStatus={handleBulkStatus}
            theme={theme}
            currentUserName={user?.display_name || user?.username || 'Operator'}
            dataSource={dataSource}
            isBackendOnline={isBackendOnline}
            refreshKey={alertsRefreshKey}
          />
        );
      case 'admin':
        return <AdminAuditView theme={theme} />;
      case 'dp-ledger':
        return <DifferentialPrivacyControls theme={theme} />;
    }
  };

  return (
    <div data-theme={theme} className="bg-background text-on-surface font-body overflow-hidden h-screen flex w-full">
      <Sidebar
        currentView={currentView}
        setView={setView}
        theme={theme}
        toggleTheme={() => setTheme(theme === 'analytics' ? 'sovereign' : 'analytics')}
        openAlertsCount={openAlertsCount}
        dataSource={dataSource}
        setDataSource={setDataSource}
        isBackendOnline={isBackendOnline}
        apiAlertsCount={totalAlertsCount}
        apiTargetCount={dashboardData?.mule_alert_count ?? 0}
        apiDatasetCount={dashboardData?.dataset_alert_count ?? 0}
        onNewInvestigation={handleNewInvestigation}
        onLogout={logout}
        onAdmin={() => navigate('/admin')}
        userDisplayName={user?.display_name || user?.username}
        userRole={user?.role}
      />

      <main className="flex-1 flex flex-col ml-64 overflow-hidden relative">
        <header className="flex justify-between items-center w-full px-6 h-16 bg-surface border-b border-outline-variant shrink-0 z-10">
          <div className="flex items-center gap-4 relative">
            <div className="relative">
              <span className="absolute inset-y-0 left-3 flex items-center text-on-surface-variant">
                <Search size={16} />
              </span>
              <input
                className="bg-surface-container-low border border-outline-variant rounded-full pl-10 pr-4 py-1.5 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/40 w-64 text-on-surface placeholder:text-on-surface-variant/50 transition-all duration-150 ease-out"
                placeholder="Search alerts, accounts..."
                type="text"
                value={globalSearch}
                onChange={e => setGlobalSearch(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                aria-label="Search alerts and accounts"
              />
            </div>
            {globalSearch.trim() && (
              <div className="absolute top-full left-0 mt-2 w-80 max-h-64 overflow-y-auto bg-surface border border-outline-variant rounded-xl shadow-xl z-50 custom-scrollbar">
                {searchResults.length === 0 ? (
                  <p className="p-3 text-xs text-on-surface-variant">No matches for &ldquo;{globalSearch}&rdquo;</p>
                ) : (
                  searchResults.slice(0, 8).map(a => (
                    <button
                      key={a.id}
                      onClick={() => handleSelectAlert(a.id)}
                      className="w-full text-left px-3 py-2.5 hover:bg-surface-container-high border-b border-outline-variant/30 last:border-0 transition-colors"
                    >
                      <div className="text-xs font-bold text-primary">{a.id}</div>
                      <div className="text-[10px] text-on-surface-variant">
                        {a.accountNumber} · {a.type} · Score {a.riskScore}
                      </div>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-headline font-black text-primary mr-4">FAGE Workbench</span>
            <button
              onClick={() => navigate('/alerts')}
              title={`${openAlertsCount} open alerts`}
              className="relative p-2 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface rounded-full cursor-pointer transition-all"
            >
              <Bell size={18} />
              {openAlertsCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-error text-on-error text-[9px] font-black flex items-center justify-center">
                  {openAlertsCount > 99 ? '99+' : openAlertsCount}
                </span>
              )}
            </button>
            <button
              onClick={() => setShowHelp(true)}
              title="Keyboard shortcuts & help"
              className="p-2 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface rounded-full cursor-pointer transition-all"
            >
              <HelpCircle size={18} />
            </button>
            <button
              title={user?.display_name || 'Operator'}
              className="h-8 w-8 rounded-full bg-primary overflow-hidden ml-2 ring-2 ring-outline-variant flex items-center justify-center font-bold text-on-primary text-[10px]"
            >
              {(user?.username || 'AD').slice(0, 2).toUpperCase()}
            </button>
          </div>
        </header>

        <div className="flex-1 relative overflow-hidden">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.22, ease: [0.25, 0.46, 0.45, 0.94] }}
              className={
                currentView === 'investigation'
                  ? 'absolute inset-0 flex overflow-hidden'
                  : 'absolute inset-0 overflow-y-auto p-6 block w-full h-full custom-scrollbar'
              }
            >
              <ErrorBoundary onReset={() => navigate('/alerts')}>
                {renderView()}
              </ErrorBoundary>
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      {showHelp && (
        <div className="fixed inset-0 z-[100] bg-black/50 flex items-center justify-center p-4" onClick={() => setShowHelp(false)}>
          <div
            className="bg-surface border border-outline-variant rounded-xl p-6 max-w-md w-full shadow-2xl"
            onClick={e => e.stopPropagation()}
            data-theme={theme}
          >
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-on-surface">Operator shortcuts</h3>
              <button onClick={() => setShowHelp(false)} className="p-1 rounded hover:bg-surface-container-high">
                <X size={16} />
              </button>
            </div>
            <ul className="space-y-2 text-sm text-on-surface-variant">
              <li><kbd className="px-1.5 py-0.5 bg-surface-container border border-outline rounded text-xs font-mono">J</kbd> / <kbd className="px-1.5 py-0.5 bg-surface-container border border-outline rounded text-xs font-mono">K</kbd> Next / previous alert</li>
              <li><kbd className="px-1.5 py-0.5 bg-surface-container border border-outline rounded text-xs font-mono">E</kbd> Escalate</li>
              <li><kbd className="px-1.5 py-0.5 bg-surface-container border border-outline rounded text-xs font-mono">C</kbd> Close</li>
              <li>Deep links: <code className="text-primary text-xs">/investigation/&lt;alert-id&gt;</code></li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <LoginView />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Navigate to="/dashboard" replace />
          </RequireAuth>
        }
      />
      <Route
        path="/investigation/:alertId"
        element={
          <RequireAuth>
            <WorkbenchShell />
          </RequireAuth>
        }
      />
      <Route
        path="/:view"
        element={
          <RequireAuth>
            <WorkbenchShell />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
