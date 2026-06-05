import React from 'react';
import { 
  LayoutDashboard, 
  Search, 
  ShieldAlert, 
  Brain, 
  BarChart3, 
  Activity, 
  Bell, 
  Contrast, 
  User, 
  Shield 
} from 'lucide-react';
import { ViewMode, SystemTheme, DataSourceType } from '../types';
import logo from '../assets/logo.png';

interface SidebarProps {
  currentView: ViewMode;
  setView: (view: ViewMode) => void;
  theme: SystemTheme;
  toggleTheme: () => void;
  openAlertsCount: number;
  dataSource: DataSourceType;
  setDataSource: (source: DataSourceType) => void;
  isBackendOnline: boolean;
  apiAlertsCount: number;
  apiTargetCount: number;
  apiDatasetCount: number;
}

export default function Sidebar({ 
  currentView, 
  setView, 
  theme, 
  toggleTheme,
  openAlertsCount,
  dataSource,
  setDataSource,
  isBackendOnline,
  apiAlertsCount,
  apiTargetCount,
  apiDatasetCount
}: SidebarProps) {
  const isDark = theme === 'sovereign';

  const menuItems = [
    { id: 'dashboard' as ViewMode, label: 'Dashboard', icon: LayoutDashboard },
    { id: 'investigation' as ViewMode, label: 'Investigation Workbench', icon: Search },
    { id: 'explorer' as ViewMode, label: 'Risk Explorer', icon: Shield },
    { id: 'insights' as ViewMode, label: 'Model Insights', icon: Brain },
    { id: 'fraud' as ViewMode, label: 'Fraud Insights', icon: ShieldAlert },
    { id: 'performance' as ViewMode, label: 'Model Performance', icon: Activity },
    { id: 'alerts' as ViewMode, label: 'Alerts Queue', icon: Bell, badge: openAlertsCount }
  ];

  const sidebarClass = isDark
    ? 'bg-[#0a1220] text-slate-300 border-r border-slate-800'
    : 'bg-[#f4f2fc] text-slate-700 border-r border-[#c4c5d5]';

  return (
    <>
      {/* Mobile Header Tab */}
      <header className={`md:hidden shrink-0 h-16 w-full flex items-center justify-between px-4 border-b ${
        isDark ? 'bg-[#0f172a] border-slate-800' : 'bg-[#fbf8ff] border-[#c4c5d5]'
      } sticky top-0 z-50`}>
        <div className="flex items-center gap-2">
          <img src={logo} alt="FAGE Logo" className="h-10 w-10 object-contain" />
          <div>
            <h1 className="text-md font-extrabold font-mono text-[#1e40af] dark:text-[#bec6e0]">FAGE</h1>
            <p className="text-[9px] uppercase tracking-wider text-slate-400 font-semibold">SOVEREIGN DETECTOR</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Theme switcher */}
          <button 
            onClick={toggleTheme}
            className={`p-2 rounded-full transition-all duration-300 ${
              isDark ? 'hover:bg-slate-800 text-cyan-400' : 'hover:bg-slate-200 text-[#00288e]'
            }`}
            title="Toggle Visual Theme"
          >
            <Contrast size={18} />
          </button>
          
          <div className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold leading-none ${
            isDark ? 'bg-slate-800 text-slate-300' : 'bg-[#dde1ff] text-[#001453]'
          }`}>
            JD
          </div>
        </div>
      </header>

      {/* Desktop Sidebar menu */}
      <aside className={`hidden md:flex flex-col h-screen w-64 p-4 shrink-0 justify-between relative ${sidebarClass} z-20`}>
        <div className="space-y-6">
          {/* Platform Brand */}
          <div className="flex items-center gap-3 px-2 py-4">
            <img src={logo} alt="FAGE Logo" className="h-12 w-12 object-contain scale-100 transition-transform hover:scale-105 duration-200" />
            <div className="overflow-hidden">
              <h1 className={`text-lg font-extrabold tracking-tight leading-none ${
                isDark ? 'text-[#bec6e0]' : 'text-[#00288e]'
              }`}>FAGE</h1>
              <span className={`text-[10px] leading-tight block truncate mt-1 ${
                isDark ? 'text-slate-400' : 'text-[#757684]'
              }`}>
                Mule Account Detection Platform
              </span>
            </div>
          </div>

          {/* Navigation Links List */}
          <nav className="space-y-1">
            {menuItems.map((item) => {
              const IconComp = item.icon;
              const isActive = currentView === item.id;
              
              let linkClass = "flex items-center w-full px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all group duration-200 ";
              
              if (isActive) {
                if (isDark) {
                  linkClass += "bg-gradient-to-r from-cyan-950/40 to-transparent border-l-2 border-cyan-400 text-cyan-400 font-bold ";
                } else {
                  linkClass += "bg-[#secondary-container] bg-[#dde1ff] text-[#00288e] border-l-2 border-[#1e40af] font-bold shadow-sm ";
                }
              } else {
                if (isDark) {
                  linkClass += "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200";
                } else {
                  linkClass += "text-slate-600 hover:bg-slate-200/60 hover:text-slate-900";
                }
              }

              return (
                <button
                  key={item.id}
                  onClick={() => setView(item.id)}
                  className={linkClass}
                >
                  <IconComp 
                    className={`mr-3 shrink-0 transition-colors ${
                      isActive 
                        ? (isDark ? 'text-cyan-400' : 'text-[#1e40af]') 
                        : (isDark ? 'text-slate-400 group-hover:text-slate-200' : 'text-slate-500 group-hover:text-slate-900')
                    }`}
                    size={17}
                  />
                  <span className="truncate">{item.label}</span>
                  {item.badge && (
                    <span className="ml-auto inline-flex items-center justify-center px-1.5 py-0.5 rounded-full text-[9px] font-bold leading-none bg-[#ba1a1a] text-white">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Active Data Stream Selector */}
          <div className={`p-3 rounded-lg border space-y-2.5 transition-all duration-300 ${
            isDark 
              ? 'bg-slate-900/30 border-slate-800/80 text-slate-300' 
              : 'bg-white border-[#c4c5d5]/60 text-slate-800 shadow-sm'
          }`}>
            <div className="flex items-center justify-between">
              <span className={`text-[10px] font-bold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-[#757684]'}`}>
                Data Stream
              </span>
              <span className={`inline-flex items-center gap-1 text-[9px] font-extrabold ${
                isBackendOnline ? 'text-emerald-500' : 'text-amber-500'
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full bg-current ${isBackendOnline ? 'animate-pulse' : ''}`} />
                {isBackendOnline ? 'Live API' : 'Offline'}
              </span>
            </div>

            <div className="relative">
              <select
                value={dataSource}
                onChange={(e) => setDataSource(e.target.value as DataSourceType)}
                className={`w-full appearance-none font-sans text-xs px-2.5 py-1.5 pr-8 rounded-md outline-none cursor-pointer border transition-colors ${
                  isDark 
                    ? 'bg-slate-950 border-slate-800 text-slate-350 focus:border-cyan-500' 
                    : 'bg-slate-50 border-[#c4c5d5] text-slate-700 focus:border-[#1e40af]'
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
              <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 20 20">
                  <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Footer info & theme controller */}
        <div className="space-y-4 pt-4 border-t border-slate-300 dark:border-slate-800">
          <button
            onClick={toggleTheme}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all duration-300 ${
              isDark 
                ? 'bg-slate-800/40 text-cyan-400 hover:bg-slate-800 border border-cyan-500/10 hover:border-cyan-500/30' 
                : 'bg-white border border-[#c4c5d5] text-slate-700 hover:bg-slate-100 shadow-sm'
            }`}
          >
            <Contrast size={14} className="animate-spin-slow text-current" />
            <span>Switch Theme</span>
          </button>

          <div className="flex items-center gap-3 px-2 py-1">
            <div className={`h-9 w-9 rounded-full flex items-center justify-center font-bold text-sm ${
              isDark ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/30' : 'bg-[#dde1ff] text-[#001453]'
            }`}>
              AD
            </div>
            <div className="overflow-hidden">
              <p className={`text-xs font-bold leading-none truncate ${isDark ? 'text-slate-200' : 'text-[#1a1b22]'}`}>
                {isDark ? 'System Agent' : 'Admin'}
              </p>
              <span className={`text-[10px] mt-1 block truncate font-medium uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-[#757684]'}`}>
                {isDark ? 'LEVEL 2 ADMIN' : 'Fraud Analyst'}
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
