import React, { useState, useMemo } from 'react';
import { 
  Bell, 
  Search, 
  ChevronDown, 
  Eye, 
  Check, 
  X, 
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  ArrowRight
} from 'lucide-react';
import { Alert, SystemTheme } from '../types';

interface AlertsQueueViewProps {
  alerts: Alert[];
  onSelectAlert: (id: string) => void;
  onUpdateStatus: (id: string, status: 'Open' | 'Escalated' | 'Closed' | 'Investigating') => void;
  theme: SystemTheme;
}

export default function AlertsQueueView({ alerts, onSelectAlert, onUpdateStatus, theme }: AlertsQueueViewProps) {
  const isDark = theme === 'sovereign';
  const [activeQueueTab, setActiveQueueTab] = useState<'All' | 'Open' | 'Escalated' | 'Closed' | 'Investigating'>('All');
  const [searchWord, setSearchWord] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  // Sorting & Filtering logic
  const filteredQueue = useMemo(() => {
    return alerts.filter((a) => {
      const matchesTab = activeQueueTab === 'All' || a.status === activeQueueTab;
      const matchesSearch = 
        a.id.toLowerCase().includes(searchWord.toLowerCase()) ||
        a.accountNumber.toLowerCase().includes(searchWord.toLowerCase()) ||
        a.holderName.toLowerCase().includes(searchWord.toLowerCase());
      
      return matchesTab && matchesSearch;
    });
  }, [alerts, activeQueueTab, searchWord]);

  // Pagination bounds
  const itemsPerPage = 5;
  const totalItems = filteredQueue.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage) || 1;
  const paginatedQueue = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return filteredQueue.slice(startIndex, startIndex + itemsPerPage);
  }, [filteredQueue, currentPage]);

  const handlePageChange = (page: number) => {
    if (page < 1 || page > totalPages) return;
    setCurrentPage(page);
  };

  const getStatusStyle = (status: string) => {
    switch (status) {
      case 'Escalated':
        return 'bg-[#ffdad6] text-[#93000a] dark:bg-rose-950/40 dark:text-rose-300 border border-red-500/10';
      case 'Investigating':
        return 'bg-[#ffdbce] text-[#802a00] dark:bg-amber-950/45 dark:text-amber-300 border border-amber-500/10';
      case 'Closed':
        return 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400 border border-slate-700/10';
      default: // Open
        return 'bg-blue-50 text-blue-800 dark:bg-[#1e293b] dark:text-cyan-400 border border-cyan-500/10';
    }
  };

  return (
    <div className="space-y-6">
      {/* Queues Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className={`text-2xl font-extrabold tracking-tight ${isDark ? 'text-slate-100' : 'text-[#1a1b22]'}`}>
            Alerts Queue
          </h2>
          <p className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-[#444653]'}`}>
            Monitor, assign, and transition suspicious transaction alerts.
          </p>
        </div>

        {/* Rapid Status Stats Card summary */}
        <div className="flex gap-4 text-xs font-sans">
          <div className={`p-2 px-3 border rounded-lg ${isDark ? 'bg-slate-900/30' : 'bg-slate-50'}`}>
            <span className="text-slate-400 text-[10px] block font-semibold leading-none uppercase">Total Pending</span>
            <span className={`text-lg font-black mt-1 block leading-none ${isDark ? 'text-cyan-300' : 'text-[#1e40af]'}`}>
              {alerts.filter(a => a.status !== 'Closed').length}
            </span>
          </div>
          <div className={`p-2 px-3 border rounded-lg ${isDark ? 'bg-slate-900/30' : 'bg-slate-50'}`}>
            <span className="text-slate-400 text-[10px] block font-semibold leading-none uppercase text-red-500">Escalated</span>
            <span className="text-lg font-black mt-1 block leading-none text-red-500">
              {alerts.filter(a => a.status === 'Escalated').length}
            </span>
          </div>
        </div>
      </div>

      {/* Tabs Filter Arrays selectors */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-300 dark:border-slate-800 pb-px text-xs font-sans">
        {(['All', 'Open', 'Escalated', 'Investigating', 'Closed'] as const).map((tab) => {
          const isActive = activeQueueTab === tab;
          const count = tab === 'All' ? alerts.length : alerts.filter(a => a.status === tab).length;

          let btnClass = "px-4 py-2.5 font-bold transition-all relative leading-none border-b-2 ";
          if (isActive) {
            btnClass += isDark ? "border-cyan-400 text-cyan-400 font-extrabold" : "border-[#1e40af] text-[#1e40af] font-extrabold";
          } else {
            btnClass += "border-transparent text-slate-400 hover:text-slate-200";
          }

          return (
            <button
              key={tab}
              onClick={() => { setActiveQueueTab(tab); setCurrentPage(1); }}
              className={btnClass}
            >
              <span className="mr-1.5">{tab}</span>
              <span className={`px-1.5 py-0.5 rounded-full text-[9px] font-bold leading-none ${
                isActive 
                  ? (isDark ? 'bg-cyan-950 text-cyan-300' : 'bg-[#dde1ff] text-[#00288e]') 
                  : (isDark ? 'bg-slate-850 text-slate-400' : 'bg-slate-100 text-slate-500')
              }`}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Searching Queue bar */}
      <div className={`p-4 border rounded-xl flex items-center gap-3 ${
        isDark ? 'bg-slate-900/40 border-slate-800' : 'bg-white border-[#c4c5d5] shadow-sm'
      }`}>
        <Search size={15} className="text-slate-400" />
        <input 
          type="text"
          value={searchWord}
          onChange={(e) => { setSearchWord(e.target.value); setCurrentPage(1); }}
          placeholder="Filter queue by Alert ID, Holder Name, Account Code..."
          className={`flex-1 text-xs font-sans bg-transparent outline-none ${isDark ? 'text-slate-200' : 'text-slate-800'}`}
        />
      </div>

      {/* Main Alerts queue table list */}
      <div className={`border rounded-xl spill-hidden ${
        isDark ? 'bg-slate-900/40 border-slate-800' : 'bg-white border-[#c4c5d5] shadow-sm'
      }`}>
        <div className="table-scroll overflow-x-auto w-full">
          <table className="w-full text-left border-collapse text-xs whitespace-nowrap">
            <thead>
              <tr className={`border-b ${isDark ? 'bg-slate-900/60 border-slate-800' : 'bg-[#f4f2fc] border-[#c4c5d5]'}`}>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-widest font-mono">Alert ID</th>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-widest font-mono">Account Target</th>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-widest font-mono">Holder Name</th>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-widest font-mono">Risk Level</th>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-widest font-mono font-sans">Status</th>
                <th className="p-3 font-semibold text-slate-400 uppercase tracking-widest font-mono text-center">Triage Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-300/30 dark:divide-slate-850/60">
              {paginatedQueue.length > 0 ? (
                paginatedQueue.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-300/10 dark:hover:bg-slate-800/10 transition-colors h-14">
                    <td className="p-3 font-bold font-mono text-sky-600 dark:text-cyan-400">{a.id}</td>
                    <td className="p-3 font-mono font-semibold">{a.accountNumber}</td>
                    <td className="p-3 font-bold">{a.holderName}</td>
                    <td className="p-3">
                      <span className={`font-black font-mono ${a.riskScore >= 80 ? 'text-red-500' : 'text-slate-400'}`}>
                        {a.riskScore}/100
                      </span>
                    </td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${getStatusStyle(a.status)}`}>
                        {a.status}
                      </span>
                    </td>
                    <td className="p-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        {/* Quick Closed action */}
                        {a.status !== 'Closed' && (
                          <button
                            onClick={() => onUpdateStatus(a.id, 'Closed')}
                            className="p-1 text-slate-400 hover:text-emerald-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-all"
                            title="Decline / Dismiss case"
                          >
                            <Check size={14} />
                          </button>
                        )}
                        {/* Quick Escalated action */}
                        {a.status !== 'Escalated' && (
                          <button
                            onClick={() => onUpdateStatus(a.id, 'Escalated')}
                            className="p-1 text-slate-400 hover:text-red-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-all"
                            title="Escalate Alert priority"
                          >
                            <ShieldAlert size={14} />
                          </button>
                        )}
                        
                        <div className="w-px h-4 bg-slate-300 dark:bg-slate-800 mx-1"></div>

                        {/* Outer eye launch details */}
                        <button
                          onClick={() => onSelectAlert(a.id)}
                          className="p-1 px-2.5 text-sky-600 dark:text-cyan-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-all flex items-center gap-1 font-bold font-sans"
                        >
                          <span>Review</span>
                          <ArrowRight size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-slate-400 font-semibold font-sans">
                    No matching accounts in active queue tab.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Table footer selectors */}
        <div className={`p-4 border-t flex items-center justify-between font-sans ${
          isDark ? 'border-slate-800 bg-slate-900/20' : 'border-[#c4c5d5] bg-white text-slate-800 shadow-sm'
        }`}>
          <span className="text-xs text-slate-400 font-semibold">
            Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, totalItems)} of {totalItems} results
          </span>

          <div className="flex items-center gap-1.5 text-xs font-bold text-slate-400">
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
              className={`p-1.5 rounded border transition-colors ${
                currentPage === 1 ? 'opacity-40 cursor-not-allowed' : 'hover:bg-slate-100 text-slate-200'
              }`}
            >
              <ChevronLeft size={13} />
            </button>

            {Array.from({ length: totalPages }).map((_, i) => (
              <button
                key={i}
                onClick={() => handlePageChange(i + 1)}
                className={`w-7 h-7 flex items-center justify-center rounded transition-all ${
                  currentPage === i + 1 
                    ? (isDark ? 'bg-cyan-500 text-[#051424]' : 'bg-[#dde1ff] text-[#001453]') 
                    : (isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-100 text-slate-600')
                }`}
              >
                {i + 1}
              </button>
            ))}

            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              className={`p-1.5 rounded border transition-colors ${
                currentPage === totalPages ? 'opacity-40 cursor-not-allowed' : 'hover:bg-slate-100 text-slate-200'
              }`}
            >
              <ChevronRight size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
