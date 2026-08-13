export type ViewMode =
  | 'dashboard'
  | 'investigation'
  | 'explorer'
  | 'insights'
  | 'performance'
  | 'alerts'
  | 'admin';

export type SystemTheme = 'analytics' | 'sovereign';

export type DataSourceType = 'live-all' | 'live-target' | 'live-dataset';

interface RiskDriver {
  feature: string;
  importance_attribution: number;
  direction: 'increases_risk' | 'reduces_risk';
  raw_value: number;
}

interface ConfidenceInterval {
  lower: number | null;
  upper: number | null;
  width: number | null;
  note: string;
}

interface EvasionResistance {
  evadable_within_search?: boolean;
  features_required_to_change?: number;
  changed_features?: Array<{ feature: string; original_value: number; typical_legitimate_value: number }>;
  features_tried?: number;
  resulting_probability?: number;
  interpretation: string;
}

export interface TriageDecision {
  account_id?: string;
  risk_score?: number;
  pu_probability?: number;
  ci_lower?: number;
  ci_upper?: number;
  ci_width?: number;
  evadable?: boolean;
  triage_action?: 'FAST_TRACK_FREEZE' | 'PRIORITY_MANUAL_REVIEW' | 'INDEPENDENT_SIGNAL_CHECK' | 'STANDARD_MONITORING';
  priority_tier?: string;
  rationale?: string;
}

export interface Alert {
  id: string;
  accountNumber: string;
  receiverAccountId: string;
  type: string;
  riskScore: number;
  confidence: string;
  confidenceVal: number;
  status: 'Open' | 'Escalated' | 'Closed' | 'Investigating';
  timestamp: string;
  dateOpened?: string;
  transactionAmount: number;
  prio: string;
  assignedTo?: string;
  reason?: string;
  triage_action?: 'FAST_TRACK_FREEZE' | 'PRIORITY_MANUAL_REVIEW' | 'INDEPENDENT_SIGNAL_CHECK' | 'STANDARD_MONITORING';
  priority_tier?: string;
  pu_probability?: number;
  logs?: Array<{ operator: string; action: string; timestamp: string }>;
  sar_report?: string;
  keyRiskDrivers: RiskDriver[];
  confidenceInterval: ConfidenceInterval | null;
  evasionResistance: EvasionResistance | null;
  triageDecision: TriageDecision | null;
  hasRealExplainability: boolean;
}

export interface SHAPDriver {
  featureId: string;
  name: string;
  type: 'Behavioral' | 'Network' | 'Profile' | 'Technical';
  shapValue: number; // impact value (SHAP)
  importanceScore: number;
  value: string;
}

export interface InvestigationEvidence {
  type: 'model_confidence' | 'shap_driver' | 'rule_trigger' | 'network_simulation';
  text: string;
}

export interface RiskDecomposition {
  model_pct: number;
  rules_pct: number;
  note: string;
  network_simulation_indicator?: {
    circular_flow_detected: boolean;
    suspicious_neighbor_count: number;
    note: string;
  };
}

export interface InvestigationSummary {
  risk_score_pct: number;
  risk_tier: string;
  risk_decomposition: RiskDecomposition;
  evidence: InvestigationEvidence[];
  assessment: string;
  recommended_actions: string[];
  triage_rationale?: string | null;
  data_provenance_note: string;
}

export interface CircularFlow {
  cycle_accounts: string[];
  cycle_length: number;
  total_amount_circulated: number;
  time_window_seconds: number;
  transactions: Array<{ from: string; to: string; alert_id: string; amount: number; timestamp: number }>;
  risk_score_contribution: number;
}

export interface NetworkIntelligence {
  cluster_size: number;
  degree_centrality: Record<string, number>;
  betweenness_centrality: Record<string, number>;
  suspicious_neighbor_count: Record<string, number>;
  network_depth: number;
}

export interface SimilarCase {
  alert_id: string;
  similarity_pct: number;
  risk_tier: string;
  risk_score: number;
  status: string;
  top_shap_drivers: string[];
  timestamp: string;
}

export interface SimilarCasesResponse {
  target_alert: string;
  similar_cases: SimilarCase[];
  method: string;
  note: string;
}

export interface AnalystNote {
  id: string;
  author: string;
  timestamp: string;
  content: string;
  isSystem: boolean;
}
