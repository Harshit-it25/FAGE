import { useState, useEffect, useCallback, useRef } from 'react';
import { SystemConfig } from '../types';
import {
  fageApi,
  DashboardTelemetryResponse,
  ModelMetricsResponse,
  FeatureImportanceResponse,
  RiskScoreRequest,
  ScorecardResponse,
  AlertsResponse,
  AlertInfo,
  AlertUpdateRequest,
} from '../services/api';

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
    const interval = setInterval(() => fetchSummary(true), 30000);
    return () => clearInterval(interval);
  }, [fetchSummary]);

  return { data, loading, error, refetch: fetchSummary };
}

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

export function useFeatureImportance() {
  const [data, setData] = useState<FeatureImportanceResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchImportance = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fageApi.getFeatureImportance();
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch feature importance profiles');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchImportance();
  }, [fetchImportance]);

  return { data, loading, error, refetch: fetchImportance };
}



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

export function useAlerts(filters?: {
  status_filter?: string;
  severity_filter?: string;
  source_filter?: 'all' | 'target' | 'dataset';
  search?: string;
  assigned_to?: string;
  min_score?: number;
  max_score?: number;
  limit?: number;
  offset?: number;
  enabled?: boolean;
}) {
  const [alerts, setAlerts] = useState<AlertInfo[]>([]);
  const [count, setCount] = useState<number>(0);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isReachable, setIsReachable] = useState<boolean>(false);

  const status_filter = filters?.status_filter;
  const severity_filter = filters?.severity_filter;
  const source_filter = filters?.source_filter;
  const search = filters?.search;
  const assigned_to = filters?.assigned_to;
  const min_score = filters?.min_score;
  const max_score = filters?.max_score;
  const limit = filters?.limit;
  const offset = filters?.offset;
  const enabled = filters?.enabled ?? true;

  const isFetchingRef = useRef(false);

  const fetchAlerts = useCallback(async (isSilent: boolean = false) => {
    if (!enabled) return;
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    try {
      if (!isSilent) setLoading(true);
      if (!isSilent) setError(null);
      const res = await fageApi.listAlertsQueue({
        status_filter,
        severity_filter,
        source_filter,
        search,
        assigned_to,
        min_score,
        max_score,
        limit,
        offset,
      });
      setAlerts(res.alerts);
      setCount(res.alerts_count);
      setTotalCount(res.total_count);
      setIsReachable(true);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch alerts queue');
      setIsReachable(false);
    } finally {
      if (!isSilent) setLoading(false);
      isFetchingRef.current = false;
    }
  }, [status_filter, severity_filter, source_filter, search, assigned_to, min_score, max_score, limit, offset, enabled]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    fetchAlerts(false);
    
    const interval = setInterval(() => fetchAlerts(true), 60000);
    
    let sse: EventSource | null = null;
    try {
      sse = fageApi.connectAlertStream();
      sse.onmessage = (event) => {
        fetchAlerts(true);
      };
      sse.onerror = (err) => {
        console.warn('SSE stream error, falling back to polling.', err);
        sse?.close();
      };
    } catch (e) {
      console.warn('Failed to setup SSE stream', e);
    }

    return () => {
      clearInterval(interval);
      if (sse) sse.close();
    };
  }, [fetchAlerts, enabled]);

  return { alerts, count, totalCount, loading, error, isReachable, refetch: fetchAlerts };
}

export function useAlertById(alertId: string | undefined) {
  const [alert, setAlert] = useState<AlertInfo | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAlert = useCallback(async () => {
    if (!alertId) {
      setAlert(null);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const res = await fageApi.getAlertById(alertId);
      setAlert(res.alert);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch alert');
      setAlert(null);
    } finally {
      setLoading(false);
    }
  }, [alertId]);

  useEffect(() => {
    fetchAlert();
  }, [fetchAlert]);

  return { alert, loading, error, refetch: fetchAlert };
}

export function usePaginatedAlerts(options: {
  status_filter?: string;
  severity_filter?: string;
  source_filter?: 'all' | 'target' | 'dataset';
  search?: string;
  assigned_to?: string;
  min_score?: number;
  max_score?: number;
  page: number;
  pageSize: number;
  enabled?: boolean;
  refreshKey?: number;
}) {
  const { page, pageSize, enabled = true, refreshKey = 0, ...filters } = options;
  const offset = (page - 1) * pageSize;

  const { alerts, totalCount, loading, error, refetch } = useAlerts({
    ...filters,
    limit: pageSize,
    offset,
    enabled,
  });

  useEffect(() => {
    if (enabled && refreshKey > 0) {
      refetch(false);
    }
  }, [refreshKey, enabled, refetch]);

  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  return { alerts, totalCount, totalPages, loading, error, refetch };
}

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

export function useCostThresholds() {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCostThresholds = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fageApi.getCostThresholds();
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch cost-sensitive thresholds');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCostThresholds();
  }, [fetchCostThresholds]);

  return { data, loading, error, refetch: fetchCostThresholds };
}

export function usePUCalibration() {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPUCalibration = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fageApi.getPUCalibration();
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch PU calibration metrics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPUCalibration();
  }, [fetchPUCalibration]);

  return { data, loading, error, refetch: fetchPUCalibration };
}

export function useModelRegistry() {
  const [data, setData] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRegistry = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fageApi.getModelRegistry();
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch model registry');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRegistry();
  }, [fetchRegistry]);

  return { data, loading, error, refetch: fetchRegistry };
}



export function useSystemConfig() {
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    fageApi.getConfig()
      .then(data => {
        if (mounted) {
          setConfig(data);
          setLoading(false);
        }
      })
      .catch(err => {
        if (mounted) {
          console.error("Failed to fetch system config:", err);
          setError(err.message || 'Error fetching system config');
          setLoading(false);
        }
      });
    return () => { mounted = false; };
  }, []);

  return { config, loading, error };
}
