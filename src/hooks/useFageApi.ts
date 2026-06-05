import { useState, useEffect, useCallback } from 'react';
import {
  fageApi,
  DashboardTelemetryResponse,
  ModelMetricsResponse,
  FeatureImportanceResponse,
  PredictRequest,
  PredictResponse,
  ExplainResponse,
  RiskScoreRequest,
  ScorecardResponse,
  AlertsResponse,
  AlertInfo,
  AlertUpdateRequest,
} from '../services/api';

/**
 * Custom Hook: Fetches aggregated dashboard telemetry metrics.
 */
export function useDashboardSummary() {
  const [data, setData] = useState<DashboardTelemetryResponse['telemetry'] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async (isSilent: boolean = false) => {
    try {
      if (!isSilent) setLoading(true);
      setError(null);
      const res = await fageApi.getDashboardSummary();
      setData(res.telemetry);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch dashboard summary');
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary(false);
    const interval = setInterval(() => fetchSummary(true), 3000);
    return () => clearInterval(interval);
  }, [fetchSummary]);

  return { data, loading, error, refetch: fetchSummary };
}

/**
 * Custom Hook: Fetches all performance evaluation indicators across models.
 */
export function useModelMetrics() {
  const [data, setData] = useState<ModelMetricsResponse['models'] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fageApi.getModelMetrics();
      setData(res.models);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch model metrics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  return { data, loading, error, refetch: fetchMetrics };
}

/**
 * Custom Hook: Fetches global Shapley feature importance metrics and beeswarm coordinates.
 */
export function useFeatureImportance(modelName: string = 'XGBoost') {
  const [data, setData] = useState<FeatureImportanceResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchImportance = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fageApi.getFeatureImportance(modelName);
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch feature importance profiles');
    } finally {
      setLoading(false);
    }
  }, [modelName]);

  useEffect(() => {
    fetchImportance();
  }, [fetchImportance]);

  return { data, loading, error, refetch: fetchImportance };
}

/**
 * Custom Hook: Manages live model probability prediction flows (Inference Mutation).
 */
export function usePredict() {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictResponse['inference'] | null>(null);

  const predict = async (payload: PredictRequest) => {
    try {
      setLoading(true);
      setError(null);
      const res = await fageApi.predictFraudProbability(payload);
      setResult(res.inference);
      return res.inference;
    } catch (err: any) {
      setError(err?.message || 'Failed to trigger model inference');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setResult(null);
    setError(null);
  };

  return { predict, result, loading, error, reset };
}

/**
 * Custom Hook: Computes instanced local details and waterfall steps (Explainability Mutation).
 */
export function useExplain() {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExplainResponse | null>(null);

  const explain = async (payload: PredictRequest) => {
    try {
      setLoading(true);
      setError(null);
      const res = await fageApi.explainCaseAttribution(payload);
      setResult(res);
      return res;
    } catch (err: any) {
      setError(err?.message || 'Failed to compute file explain attributions');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setResult(null);
    setError(null);
  };

  return { explain, result, loading, error, reset };
}

/**
 * Custom Hook: Triggers combined ML and policy risk decisions (Risk Assessment Mutation).
 */
export function useRiskScore() {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScorecardResponse['scorecard'] | null>(null);

  const evaluate = async (payload: RiskScoreRequest) => {
    try {
      setLoading(true);
      setError(null);
      const res = await fageApi.scoreAndEvaluateTransaction(payload);
      setResult(res.scorecard);
      return res.scorecard;
    } catch (err: any) {
      setError(err?.message || 'Risk scoring assessment execution error');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setResult(null);
    setError(null);
  };

  return { evaluate, result, loading, error, reset };
}

/**
 * Custom Hook: Fetches, indexes, and queries incident alert queues with reactive polling.
 */
export function useAlerts(filters?: {
  status_filter?: string;
  severity_filter?: string;
  limit?: number;
}) {
  const [alerts, setAlerts] = useState<AlertInfo[]>([]);
  const [count, setCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const status_filter = filters?.status_filter;
  const severity_filter = filters?.severity_filter;
  const limit = filters?.limit;

  const fetchAlerts = useCallback(async (isSilent: boolean = false) => {
    try {
      if (!isSilent) setLoading(true);
      setError(null);
      const res = await fageApi.listAlertsQueue({
        status_filter,
        severity_filter,
        limit,
      });
      setAlerts(res.alerts);
      setCount(res.alerts_count);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch alerts queue');
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, [status_filter, severity_filter, limit]);

  useEffect(() => {
    fetchAlerts(false);
    const interval = setInterval(() => fetchAlerts(true), 3000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  return { alerts, count, loading, error, refetch: fetchAlerts };
}

/**
 * Custom Hook: Applies updates and inputs case notes to individual triggers (Alert Mutation).
 */
export function useUpdateAlert() {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAlert, setUpdatedAlert] = useState<AlertInfo | null>(null);

  const updateAlert = async (alertId: string, payload: AlertUpdateRequest) => {
    try {
      setLoading(true);
      setError(null);
      const res = await fageApi.updateAlertStatus(alertId, payload);
      setUpdatedAlert(res.alert);
      return res.alert;
    } catch (err: any) {
      setError(err?.message || `Failed to update alert: ${alertId}`);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setUpdatedAlert(null);
    setError(null);
  };

  return { updateAlert, updatedAlert, loading, error, reset };
}
