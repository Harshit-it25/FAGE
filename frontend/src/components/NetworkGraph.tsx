import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import { fageApi, CorrelateResponse } from '../services/api';
import { SystemTheme } from '../types';

interface NetworkGraphProps {
  alertId: string;
  theme?: SystemTheme;
  isGlobal?: boolean;
}

export const NetworkGraph: React.FC<NetworkGraphProps> = ({ alertId, theme }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  // Keep stable DataSet references so vis-network updates nodes in-place (no position scramble)
  const nodesDataRef = useRef<InstanceType<typeof DataSet> | null>(null);
  const edgesDataRef = useRef<InstanceType<typeof DataSet> | null>(null);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<CorrelateResponse | null>(null);
  const [physicsEnabled, setPhysicsEnabled] = useState(true);

  const isDark = theme !== 'sovereign';

  // Fetch only when alertId changes — never on theme change
  useEffect(() => {
    const fetchCorrelation = async () => {
      setLoading(true);
      try {
        const res = await fageApi.correlateAlert(alertId);
        setData(res);
      } catch (err) {
        console.error("Correlation error", err);
      } finally {
        setLoading(false);
      }
    };
    if (alertId) {
      fetchCorrelation();
    }
  }, [alertId]);

  // Build graph only when DATA changes (not theme). Theme changes call updateNodeColors() below.
  useEffect(() => {
    if (containerRef.current && data) {
      const nodesMap = new Map<string, any>();
      const edges: any[] = [];

      const labelColor = isDark ? '#ffffff' : '#0f1c22';
      const edgeColor = isDark ? '#4cd7f6' : '#006880';
      const edgeColorDim = isDark ? '#64748b' : '#6f8a97';
      // Helper to add Account nodes
      const addAccountNode = (id: string, labelPrefix: string) => {
        if (!nodesMap.has(id)) {
          const isUnknown = !id || id.includes('SENDER') || id.includes('RECEIVER');
          const displayId = isUnknown ? 'Data Unavailable' : id;
          nodesMap.set(id, {
            id,
            label: `${labelPrefix}:\n${displayId}`,
            color: { background: isDark ? '#06b6d4' : '#006880', border: isDark ? '#00424f' : '#003640' },
            font: { color: '#ffffff', face: 'monospace', size: 11, bold: true },
            shape: 'ellipse',
            shadow: true,
            title: isUnknown ? 'Simulation mode — relational fields not provided by source dataset' : `Account: ${displayId}`
          });
        }
      };

      const targetSenderId = data.target_sender || `${data.target_alert}-SENDER`;
      const targetReceiverId = data.target_receiver || `${data.target_alert}-RECEIVER`;

      // 1. Central Investigation Event Node
      nodesMap.set(data.target_alert, {
        id: data.target_alert,
        label: `Flagged Transaction:\n${data.target_alert}`,
        color: { background: '#ef4444', border: '#b91c1c' },
        font: { color: '#ffffff', face: 'monospace', size: 12, bold: true },
        shape: 'box',
        shadow: true,
        title: `Investigation Event ID: ${data.target_alert}`
      });

      // Connect Target Alert to its sender and receiver
      addAccountNode(targetSenderId, 'Origin Account');
      addAccountNode(targetReceiverId, 'Destination Account');
      
      edges.push({
        from: targetSenderId,
        to: data.target_alert,
        label: '[INVESTIGATION SIMULATION]\nTransaction Initiation',
        font: { color: labelColor, size: 9, align: 'middle' },
        color: { color: edgeColor, opacity: 0.8 },
        arrows: { to: { enabled: true, scaleFactor: 0.5 } }
      });
      edges.push({
        from: data.target_alert,
        to: targetReceiverId,
        label: '[INVESTIGATION SIMULATION]\nFund Transfer',
        font: { color: labelColor, size: 9, align: 'middle' },
        color: { color: edgeColor, opacity: 0.8 },
        arrows: { to: { enabled: true, scaleFactor: 0.5 } }
      });

      // 2. Map Related Entities
      if (data.related_entities && data.related_entities.length > 0) {
        data.related_entities.forEach((entity) => {
          const amtText = entity.amount ? `\n₹${entity.amount.toLocaleString('en-IN')}` : '';
          
          nodesMap.set(entity.alert_id, {
            id: entity.alert_id,
            label: `Investigation Event:\n${entity.alert_id}${amtText}`,
            color: {
              background: entity.severity === 'Critical' ? '#f97316' : entity.severity === 'High' ? '#eab308' : '#3b82f6',
              border: isDark ? '#334155' : '#cbd5e1'
            },
            font: { color: '#ffffff', face: 'monospace', size: 11 },
            shape: 'box',
            shadow: true,
            title: `Event: ${entity.alert_id} | Match: ${(entity.match_reasons || []).join('; ')}`
          });

          const senderId = entity.sender_id || `${entity.alert_id}-SENDER`;
          const receiverId = entity.receiver_id || `${entity.alert_id}-RECEIVER`;
          addAccountNode(senderId, 'Origin Account');
          addAccountNode(receiverId, 'Destination Account');

          edges.push({
            from: senderId,
            to: entity.alert_id,
            label: '[SIMULATION]\nTxn Initiation',
            font: { color: labelColor, size: 9, align: 'middle' },
            color: { color: edgeColorDim, opacity: 0.8 },
            arrows: { to: { enabled: true, scaleFactor: 0.5 } }
          });
          edges.push({
            from: entity.alert_id,
            to: receiverId,
            label: '[SIMULATION]\nFund Transfer',
            font: { color: labelColor, size: 9, align: 'middle' },
            color: { color: edgeColorDim, opacity: 0.8 },
            arrows: { to: { enabled: true, scaleFactor: 0.5 } }
          });

          // Draw explicit simulated behavioral links if bridge_entity is a behavioral heuristic
          if (entity.bridge_entity && (entity.bridge_entity.includes('PATTERN') || entity.bridge_entity.includes('BAND'))) {
            const bridgeId = entity.bridge_entity;
            if (!nodesMap.has(bridgeId)) {
              nodesMap.set(bridgeId, {
                id: bridgeId,
                label: `Potential Network Pattern:\n${bridgeId.replace(/_/g, ' ')}`,
                color: { background: '#a855f7', border: '#7e22ce' },
                font: { color: '#ffffff', face: 'monospace', size: 11, bold: true },
                shape: 'diamond',
                shadow: true,
                title: `[INVESTIGATION SIMULATION] Heuristic Match`
              });
              edges.push({
                from: data.target_alert,
                to: bridgeId,
                label: '[SIMULATION]\nPattern Match',
                font: { color: isDark ? '#c084fc' : '#7e22ce', size: 10, align: 'middle' },
                color: { color: isDark ? '#a855f7' : '#7e22ce', opacity: 0.9 },
                dashes: true
              });
            }
            edges.push({
              from: bridgeId,
              to: entity.alert_id,
              label: `[SIMULATION]\n${(entity.match_reasons && entity.match_reasons[0])?.slice(0, 35) || 'Match'}...`,
              font: { color: labelColor, size: 10, align: 'middle' },
              color: { color: edgeColorDim, opacity: 0.8 },
              dashes: true
            });
          }
        });
      }

      const nodesArray = Array.from(nodesMap.values());

      if (networkRef.current && nodesDataRef.current && edgesDataRef.current) {
        // Graph already exists for this alert — just update the datasets in-place (preserves positions)
        nodesDataRef.current.clear();
        nodesDataRef.current.add(nodesArray);
        edgesDataRef.current.clear();
        edgesDataRef.current.add(edges);
      } else {
        // First render for this alert — create fresh Network
        const ds_nodes = new DataSet(nodesArray);
        const ds_edges = new DataSet(edges);
        nodesDataRef.current = ds_nodes;
        edgesDataRef.current = ds_edges;

        const options: any = {
          physics: {
            enabled: physicsEnabled,
            stabilization: true,
            barnesHut: { gravitationalConstant: -3000, springConstant: 0.045, springLength: 150 }
          },
          interaction: { hover: true, zoomView: true, dragNodes: true },
          edges: { smooth: { enabled: true, type: 'continuous', roundness: 0.35 } }
        };

        const network = new Network(containerRef.current!, { nodes: ds_nodes, edges: ds_edges }, options);
        networkRef.current = network;
      }

      return () => {
        if (networkRef.current) {
          networkRef.current.destroy();
          networkRef.current = null;
          nodesDataRef.current = null;
          edgesDataRef.current = null;
        }
      };
    }
  // isDark intentionally excluded — theme changes are handled by updateNodeColors() to avoid position scramble
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  // When theme changes, update node/edge colors IN-PLACE without rebuilding (no position scramble)
  useEffect(() => {
    if (!networkRef.current || !nodesDataRef.current || !edgesDataRef.current || !data) return;

    const labelColor = isDark ? '#ffffff' : '#0f1c22';
    const edgeColor = isDark ? '#4cd7f6' : '#006880';

    // Update target alert node color
    nodesDataRef.current.update({
      id: data.target_alert,
      color: { background: '#ef4444', border: '#b91c1c' } as any,
    });

    // Update all entity nodes border colors
    if (data.related_entities) {
      data.related_entities.forEach((entity) => {
        nodesDataRef.current!.update({
          id: entity.alert_id,
          color: {
            background: entity.severity === 'Critical' ? '#f97316' : entity.severity === 'High' ? '#eab308' : '#3b82f6',
            border: isDark ? '#334155' : '#cbd5e1'
          } as any
        });
      });
    }

    // Update edge colors
    const allEdges = edgesDataRef.current.get();
    edgesDataRef.current.update(
      allEdges.map((e: any) => ({
        id: e.id,
        font: { ...e.font, color: labelColor },
        color: { ...e.color, color: edgeColor }
      }))
    );
  }, [isDark]);

  const handleZoomIn = () => {
    if (networkRef.current) {
      const scale = networkRef.current.getScale();
      networkRef.current.moveTo({ scale: scale * 1.3 });
    }
  };

  const handleZoomOut = () => {
    if (networkRef.current) {
      const scale = networkRef.current.getScale();
      networkRef.current.moveTo({ scale: scale / 1.3 });
    }
  };

  const handleFit = () => {
    if (networkRef.current) {
      networkRef.current.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
    }
  };

  const togglePhysics = () => {
    const next = !physicsEnabled;
    setPhysicsEnabled(next);
    // BUG-001 FIX: Use native vis-network setOptions instead of triggering full graph rebuild
    if (networkRef.current) {
      networkRef.current.setOptions({ physics: { enabled: next } });
    }
  };

  if (loading) {
    return (
      <div className="stitch-glass-card border border-outline-variant rounded-xl p-6 w-full flex flex-col items-center justify-center min-h-[320px] text-on-surface-variant text-sm animate-pulse">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mb-3"></div>
        Running multi-hop graph correlation, ring detection & structuring analysis...
      </div>
    );
  }

  if (!data) return null;

  const summary = data.graph_summary;

  return (
    <div className={`border rounded-xl p-4 w-full flex flex-col gap-3 shadow-sm transition-all ${
      isDark ? 'bg-surface-container-low border-outline-variant text-slate-200' : 'bg-white border-[#c4c5d5] text-slate-800'
    }`}>
      <div className="flex flex-col gap-3 border-b border-outline-variant/30 pb-3">
        {/* Title Row */}
        <div className="flex items-center gap-2 w-full min-w-0">
          <svg className="w-4 h-4 text-primary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
          <h3 className="text-sm font-bold uppercase tracking-wider truncate break-words">
            Transaction-Level Multi-Hop Correlation Graph
          </h3>
        </div>

        {/* Interactive Controls & Badges Row */}
        <div className="flex flex-wrap items-center justify-between gap-2 w-full">
          {summary && (
            <div className="flex items-center gap-1.5 text-[11px] font-mono font-bold mr-2">
              <span className={`px-2 py-0.5 rounded border ${isDark ? 'bg-slate-800 text-cyan-300 border-cyan-500/30' : 'bg-cyan-50 text-cyan-800 border-cyan-200'}`}>
                Cluster: {summary.cluster_size}
              </span>
              <span className={`px-2 py-0.5 rounded border ${isDark ? 'bg-slate-800 text-purple-300 border-purple-500/30' : 'bg-purple-50 text-purple-800 border-purple-200'}`}>
                Max Hop: {summary.max_hop_distance}
              </span>
              {(summary.bridge_nodes?.length ?? 0) > 0 && (
                <span className={`px-2 py-0.5 rounded border ${isDark ? 'bg-slate-800 text-amber-300 border-amber-500/30' : 'bg-amber-50 text-amber-800 border-amber-200'}`}>
                  Bridges: {summary.bridge_nodes?.length ?? 0}
                </span>
              )}
            </div>
          )}

          <div className="flex items-center gap-1 bg-surface-container p-1 rounded-md border border-outline-variant/40">
            <button onClick={handleZoomIn} title="Zoom In" className="px-2 py-0.5 text-xs hover:bg-primary/20 rounded font-bold transition-colors">➕</button>
            <button onClick={handleZoomOut} title="Zoom Out" className="px-2 py-0.5 text-xs hover:bg-primary/20 rounded font-bold transition-colors">➖</button>
            <button onClick={handleFit} title="Fit to View" className="px-2 py-0.5 text-[11px] font-mono font-bold hover:bg-primary/20 rounded transition-colors">FIT</button>
            <button 
              onClick={togglePhysics} 
              title={physicsEnabled ? "Freeze Layout Physics" : "Enable Physics"} 
              className={`px-2 py-0.5 text-[10px] uppercase font-bold rounded transition-colors ${physicsEnabled ? 'bg-primary text-on-primary' : 'bg-surface-container-highest text-on-surface-variant'}`}
            >
              {physicsEnabled ? "Physics ON" : "Physics OFF"}
            </button>
          </div>
        </div>
      </div>

      {summary?.structuring_detected && (
        <div className={`p-2.5 rounded-lg border text-xs flex items-center gap-2 font-sans font-semibold ${
          isDark ? 'bg-red-950/40 border-red-500/40 text-red-300' : 'bg-red-50 border-red-300 text-red-800'
        }`}>
          <span className="px-1.5 py-0.5 rounded bg-red-600 text-white font-black text-[10px] uppercase font-mono">
            Structuring Alert
          </span>
          <span>
            Multi-hop ring or velocity smurfing detected across {summary.cluster_size} accounts via intermediary bridge(s) [{(summary.bridge_nodes ?? []).join(', ')}].
          </span>
        </div>
      )}

      <div className={`p-2.5 rounded border text-xs flex flex-col gap-1 font-sans ${
        isDark ? 'bg-amber-950/40 border-amber-500/40 text-amber-300' : 'bg-amber-50 border-amber-300 text-amber-800'
      }`}>
        <div className="font-bold uppercase tracking-wider flex items-center gap-1">
          ⚠️ INVESTIGATION SIMULATION
        </div>
        <div>
          The underlying dataset lacks relational identifiers (e.g., Device ID, IP). These graph edges are mathematically synthesized for demonstration purposes and do not represent real transaction relationships.
        </div>
      </div>

      <div 
        ref={containerRef} 
        className={`w-full h-[360px] rounded border transition-colors ${
          isDark ? 'bg-[#0a0f11] border-outline-variant/40' : 'bg-[#f8fafc] border-[#cbd5e1]'
        }`} 
      />
    </div>
  );
};
