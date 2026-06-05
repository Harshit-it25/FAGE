export type ViewMode =
  | 'dashboard'
  | 'investigation'
  | 'explorer'
  | 'insights'
  | 'fraud'
  | 'performance'
  | 'alerts';

export type SystemTheme = 'analytics' | 'sovereign';

export type DataSourceType = 'live-all' | 'live-target' | 'live-dataset';

export interface Alert {
  id: string;
  accountNumber: string;
  type: string;
  riskScore: number;
  confidence: string;
  confidenceVal: number;
  status: 'Open' | 'Escalated' | 'Closed' | 'Investigating';
  timestamp: string;
  holderName: string;
  ssn: string;
  dateOpened: string;
  balance: number;
  ytdInflows: number;
  ytdOutflows: number;
  prio: string;
  assignedTo?: string;
  reason?: string;
  logs?: Array<{ operator: string; action: string; timestamp: string }>;
}

export interface SHAPDriver {
  featureId: string;
  name: string;
  type: 'Behavioral' | 'Network' | 'Profile' | 'Technical';
  shapValue: number; // impact value (SHAP)
  importanceScore: number;
  value: string;
}

export interface AnalystNote {
  id: string;
  author: string;
  timestamp: string;
  content: string;
  isSystem: boolean;
}

export interface FraudCluster {
  id: string;
  name: string;
  description: string;
  severity: 'Critical' | 'High' | 'Medium' | 'Low';
  entitiesCount: number;
  score: number;
}

export interface OutlierEvent {
  id: string;
  timestamp: string;
  patternType: string;
  severity: 'Critical' | 'High' | 'Medium' | 'Low';
}
