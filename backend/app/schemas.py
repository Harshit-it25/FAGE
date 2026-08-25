from __future__ import annotations
from typing import Dict, List, Any, Optional, Literal
from pydantic import BaseModel, Field

class PredictRequest(BaseModel):
    features: Dict[str, float] = Field(
        ..., 
        description="Key-value mapping of feature designations and quantitative value states."
    )

class RiskScoreRequest(BaseModel):
    transaction_id: Optional[str] = Field(None, max_length=128, description="Unique identification trace string.")
    sender_id: Optional[str] = Field("ACC-1102", max_length=128, description="Initiator transaction ID sequence.")
    receiver_id: Optional[str] = Field("ACC-8839", max_length=128, description="Receiver/Beneficiary account identifier.")
    amount: float = Field(..., ge=0.0, le=1_000_000_000, description="Quantitative value scale of transfer transactional volume.")
    origin_country: str = Field("US", max_length=8, description="Origin country ISO standard 2-digit code.")
    destination_country: str = Field("US", max_length=8, description="Destination country ISO standard 2-digit code.")
    account_age_days: int = Field(365, ge=0, le=100_000, description="Operational age of sending account in calendar days.")
    is_international: bool = Field(False, description="Flag setting geographical cross-border traits.")
    custom_metrics: Optional[Dict[str, float]] = Field(
        None, 
        description="Optional telemetry metrics dictionary corresponding to high-dimensional FAGE model parameters."
    )

class AlertUpdateRequest(BaseModel):
    status: Optional[Literal['Open', 'Investigating', 'Escalated', 'Closed']] = Field(None, description="Action state: Open, Investigating, Escalated, Closed.")
    notes: Optional[str] = Field(None, max_length=5000, description="Operational remarks/case ledger inputs.")
    assigned_to: Optional[str] = Field(None, max_length=128, description="Operator assignment name.")
    operator_name: Optional[str] = Field("System Operator", max_length=128, description="Name of the operator making the change.")

class AlertIngestRequest(BaseModel):
    transaction_id: str = Field(..., max_length=128, description="Unique transaction ID.")
    sender_id: Optional[str] = Field("ACC-UNKN", max_length=128, description="Sender account.")
    receiver_id: Optional[str] = Field("ACC-UNKN", max_length=128, description="Receiver account.")
    amount: float = Field(..., ge=0.0, le=1_000_000_000, description="Transaction amount.")
    risk_score: Optional[int] = Field(None, ge=0, le=100, description="1-100 risk score")
    severity: Optional[str] = Field(None, max_length=32, description="Calculated automatically if null.")
    status: Optional[Literal['Open', 'Investigating', 'Escalated', 'Closed']] = Field("Open", description="Alert status state: Open, Investigating, Escalated, Closed.")
    reason: Optional[str] = Field("Manual external legacy rule sync ingestion.", max_length=2000, description="Alert rationale.")
    timestamp: Optional[str] = Field(None, max_length=64, description="ISO timestamp string.")
    assigned_to: Optional[str] = Field("Unassigned", max_length=128, description="Operator assignment.")
    logs: Optional[List[Dict[str, Any]]] = Field(None, description="Logs audit trail.")

class SARResponse(BaseModel):
    sar_report: str
    fincen_tracking_id: Optional[str] = None
    citation_hash: Optional[str] = None

class PlainLanguageExplanationResponse(BaseModel):
    explanation: str

class TuneRequest(BaseModel):
    new_threshold: float

class PUCalibrateRequest(BaseModel):
    raw_probabilities: List[float] = Field(..., description="List of raw predicted probabilities P(s=1|x)")
    c_factor: Optional[float] = Field(None, description="Optional override label frequency c")

class SPYTuneRequest(BaseModel):
    spy_threshold: Optional[float] = Field(None, description="New reliable negative SPY threshold (0-1)")
    c_factor: Optional[float] = Field(None, description="New PU discovery probability c factor (0-1)")

class TriageEvalRequest(BaseModel):
    risk_score: float = Field(..., description="Model risk score (0-100)")
    ci_lower: float = Field(..., description="Lower bound of 90% confidence interval (0-1)")
    ci_upper: float = Field(..., description="Upper bound of 90% confidence interval (0-1)")
    evadable: bool = Field(False, description="Whether profile is evadable within 3-feature perturbation")
    pu_probability: Optional[float] = Field(None, description="PU calibrated probability (0-1)")
    account_id: Optional[str] = Field("TXN-EVAL", description="Account identifier")

class FeedbackRequest(BaseModel):
    alert_id: str = Field(..., max_length=128, description="Alert ID or Account ID being reviewed")
    label: Literal['True Positive', 'False Positive', 'Mule Ring', 'Suspicious'] = Field(..., description="Ground truth label")
    analyst_notes: Optional[str] = Field(None, max_length=5000, description="Detailed notes on investigation rationale")
    trigger_recalibration: bool = Field(True, description="Whether to trigger online PU and threshold recalibration")
    tenant_id: Optional[str] = Field("TN-GLOBAL-01", max_length=128, description="Tenant ID")
    org_id: Optional[str] = Field("ORG-FIN-PRIMARY", max_length=128, description="Organization ID")

class FeedbackResponse(BaseModel):
    status: str = "success"
    alert_id: str
    label_recorded: str
    recalibration_triggered: bool
    old_c_factor: float
    new_c_factor: float
    old_spy_threshold: Optional[float]
    new_spy_threshold: Optional[float]
    message: str

class DPExportRequest(BaseModel):
    epsilon: Optional[float] = Field(None, gt=0.0, description="Requested privacy epsilon budget")
    mechanism: str = Field("laplace", description="Noise injection mechanism ('laplace' or 'gaussian')")

class DPResetRequest(BaseModel):
    max_epsilon: Optional[float] = Field(None, gt=0.0, description="New maximum epsilon budget to allocate")

class AdversarialShiftRequest(BaseModel):
    shift_type: str = Field("micro_structuring", description="Type of distribution shift to simulate.")
    intensity: float = Field(0.6, ge=0.0, le=1.0, description="Shift intensity (0-1).")
    trigger_adaptation: bool = Field(True, description="Whether to allow adaptive recalibration if drift is detected.")

