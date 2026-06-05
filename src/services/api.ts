import axios, { AxiosInstance, AxiosResponse } from 'axios';

// Get the API base URL with fallback to window.location.origin/api or relative /api
const getBaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    // Next.js-style env var or Vite-style env var configuration
    const envUrl = 
      (window as any).__ENV__?.API_URL ||
      (import.meta as any).env?.VITE_API_URL ||
      (process as any).env?.NEXT_PUBLIC_API_URL;
      
    if (envUrl) return envUrl;
  }
  return '/api';
};

/**
 * Enterprise Axios client configured with standard timeout, headers, and interceptors.
 */
export const apiClient: AxiosInstance = axios.create({
  baseURL: getBaseUrl(),
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Configure default response interceptors for custom error handling
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    const customError = {
      message: error.response?.data?.detail || error.message || 'An unexpected API error occurred',
      status: error.response?.status,
      data: error.response?.data,
    };
    console.error('[API Integration Service Error]:', customError);
    return Promise.reject(customError);
  }
);

// ============================================================================
//                       TypeScript Interface Contracts
// ============================================================================

export interface PredictRequest {
  features: Record<string, number>;
}

export interface PredictResponse {
  status: string;
  metadata: {
    execution_timestamp: string;
    features_analyzed: number;
  };
  inference: {
    fraud_probability: number;
    predicted_class_label: number;
    decision_threshold: number;
  };
}

export interface RiskScoreRequest {
  transaction_id?: string;
  sender_id?: string;
  receiver_id?: string;
  amount: number;
  origin_country: string;
  destination_country: string;
  account_age_days: number;
  is_international: boolean;
  custom_metrics?: Record<string, number>;
}

export interface RiskDriver {
  feature: string;
  importance_attribution: number;
  direction: 'increases_risk' | 'reduces_risk';
  raw_value: number;
}

export interface WaterfallStep {
  feature: string;
  value: number;
  cumulative: number;
  type: 'base' | 'positive' | 'negative' | 'total';
  stat_label: string;
}

export interface WaterfallVisuals {
  base_value: number;
  final_value: number;
  steps: WaterfallStep[];
  model_metadata: {
    algorithm: string;
    explained_feature_count: number;
  };
}

export interface ScorecardResponse {
  status: string;
  scorecard: {
    transaction_id: string;
    timestamp: string;
    processing_metadata: {
      engine_version: string;
      selected_model: string;
      is_override_applied: boolean;
    };
    scores: {
      base_ml_score: number;
      base_ml_probability: number;
      final_risk_score: number;
    };
    categorizations: {
      risk_tier: 'Low' | 'Medium' | 'High' | 'Critical';
      alert_severity: 'Low' | 'Medium' | 'High' | 'Critical';
      action_decision: 'Approve' | 'Review' | 'Escalate' | 'Block';
    };
    rules_audit: {
      triggered_rules_count: number;
      overrides: Array<{
        rule_id: string;
        rule_name: string;
        trigger_score: number;
        tier_enforcement: string;
        alert_severity_enforcement: string;
        reason: string;
      }>;
    };
    explainability: {
      key_risk_drivers: RiskDriver[];
      waterfall_visuals: WaterfallVisuals;
    };
    associated_alert_id?: string;
  };
}

export interface ExplainResponse {
  status: string;
  attributions: Record<string, number>;
  waterfall_visuals: WaterfallVisuals;
  static_chart_base64: string;
}

export interface DashboardTelemetryResponse {
  status: string;
  compiled_at: string;
  telemetry: {
    total_incidents_recorded: number;
    average_risk_rating: number;
    maximum_index_severity: number;
    incident_status_matrix: {
      Open: number;
      Investigating: number;
      Escalated: number;
      Closed: number;
    };
    severity_profile: {
      Critical: number;
      High: number;
      Medium: number;
      Low: number;
    };
    rule_exception_rate: number;
    mule_classification_precision: number;
  };
}

export interface ModelPerformanceMetric {
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number;
  pr_auc: number;
  confusion_matrix: number[][];
}

export interface ModelMetricsResponse {
  source: string;
  models: Record<string, ModelPerformanceMetric>;
}

export interface FeatureImportanceItem {
  feature: string;
  mean_abs_attribution: number;
}

export interface BeeswarmPoint {
  feature: string;
  val: number;
  normalized_val: number;
  shap_val: number;
}

export interface FeatureImportanceResponse {
  status: string;
  model_requested: string;
  importance_profile: FeatureImportanceItem[];
  beeswarm_scatter: {
    top_features: string[];
    global_rankings: Record<string, number>;
    points: BeeswarmPoint[];
  };
  static_beeswarm_base64: string;
}

export interface AlertLog {
  operator: string;
  action: string;
  timestamp: string;
}

export interface AlertInfo {
  id: string;
  transaction_id: string;
  sender_id: string;
  receiver_id: string;
  amount: number;
  risk_score: number;
  risk_tier: 'Low' | 'Medium' | 'High' | 'Critical';
  severity: 'Low' | 'Medium' | 'High' | 'Critical';
  status: 'Open' | 'Investigating' | 'Escalated' | 'Closed';
  reason: string;
  timestamp: string;
  assigned_to: string;
  logs: AlertLog[];
}

export interface AlertsResponse {
  status: string;
  alerts_count: number;
  alerts: AlertInfo[];
}

export interface AlertUpdateRequest {
  status: 'Open' | 'Investigating' | 'Escalated' | 'Closed';
  notes?: string;
  assigned_to?: string;
}

// ============================================================================
//                         API Integration Methods
// ============================================================================

export const fageApi = {
  /**
   * Fetch aggregate operational and decision telemetry metrics for dashboards.
   */
  getDashboardSummary: async (): Promise<DashboardTelemetryResponse> => {
    const response = await apiClient.get<DashboardTelemetryResponse>('/dashboard');
    return response.data;
  },

  /**
   * Fetch performance evaluation and confusion matrix indicators across trained algorithms.
   */
  getModelMetrics: async (): Promise<ModelMetricsResponse> => {
    const response = await apiClient.get<ModelMetricsResponse>('/metrics');
    return response.data;
  },

  /**
   * Fetch global Shapley feature aggregations and scatter plot coordinates.
   */
  getFeatureImportance: async (modelName: string = 'XGBoost'): Promise<FeatureImportanceResponse> => {
    const response = await apiClient.get<FeatureImportanceResponse>('/feature-importance', {
      params: { model_name: modelName },
    });
    return response.data;
  },

  /**
   * Run immediate transactional attribute classifications.
   */
  predictFraudProbability: async (payload: PredictRequest): Promise<PredictResponse> => {
    const response = await apiClient.post<PredictResponse>('/predict', payload);
    return response.data;
  },

  /**
   * Fetch explicit local instance attributions and formatted Waterfall steps.
   */
  explainCaseAttribution: async (payload: PredictRequest): Promise<ExplainResponse> => {
    const response = await apiClient.post<ExplainResponse>('/explain', payload);
    return response.data;
  },

  /**
   * Score raw transfers against machine learning and compliance rule policies.
   */
  scoreAndEvaluateTransaction: async (payload: RiskScoreRequest): Promise<ScorecardResponse> => {
    const response = await apiClient.post<ScorecardResponse>('/risk-score', payload);
    return response.data;
  },

  /**
   * Query incident queue with optional alert filter states.
   */
  listAlertsQueue: async (filters?: {
    status_filter?: string;
    severity_filter?: string;
    limit?: number;
  }): Promise<AlertsResponse> => {
    const response = await apiClient.get<AlertsResponse>('/alerts', {
      params: filters,
    });
    return response.data;
  },

  /**
   * Push manual or legacy synchronized alert incident metrics into the audit database.
   */
  ingestSimulatedAlert: async (payload: Partial<AlertInfo>): Promise<{ status: string; created_alert_id: string }> => {
    const response = await apiClient.post<{ status: string; created_alert_id: string }>('/alerts', payload);
    return response.data;
  },

  /**
   * Apply status revisions and write analyst audit notes.
   */
  updateAlertStatus: async (alertId: string, payload: AlertUpdateRequest): Promise<{ status: string; message: string; alert: AlertInfo }> => {
    const response = await apiClient.put<{ status: string; message: string; alert: AlertInfo }>(`/alerts/${alertId}`, payload);
    return response.data;
  },
};
