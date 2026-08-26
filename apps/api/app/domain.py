from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field, field_validator

class CapabilityStatus(StrEnum):
    SUPPORTED = "SUPPORTED"; UNSUPPORTED = "UNSUPPORTED"; SIMULATED = "SIMULATED"; NOT_CONFIGURED = "NOT_CONFIGURED"

class DataMode(StrEnum):
    HISTORICAL = "HISTORICAL"; POLLING = "POLLING"; WEBHOOK = "WEBHOOK"; SUBSCRIPTION = "SUBSCRIPTION"; SIMULATED = "SIMULATED"

class Chain(StrEnum): ETHEREUM = "ethereum"

class EntityType(StrEnum):
    VASP="VASP"; EXCHANGE="EXCHANGE"; SERVICE="SERVICE"; MIXER="MIXER"; BRIDGE="BRIDGE"; PROTOCOL="PROTOCOL"; UNKNOWN="UNKNOWN"
class AttributionRole(StrEnum):
    DEPOSIT="DEPOSIT"; HOT_WALLET="HOT_WALLET"; COLD_WALLET="COLD_WALLET"; TREASURY="TREASURY"; CONTRACT="CONTRACT"; SERVICE="SERVICE"; UNKNOWN="UNKNOWN"
class ConfidenceLevel(StrEnum):
    UNKNOWN="UNKNOWN"; LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"; CONFIRMED="CONFIRMED"

class PatternType(StrEnum):
    RAPID_HOP="RAPID_HOP"; FAN_OUT="FAN_OUT"; FAN_IN="FAN_IN"; PEEL_CHAIN="PEEL_CHAIN"
    CONSOLIDATION="CONSOLIDATION"; BURST_ACTIVITY="BURST_ACTIVITY"; DORMANT_ACTIVATION="DORMANT_ACTIVATION"
    MIXER_INTERACTION="MIXER_INTERACTION"; BRIDGE_INTERACTION="BRIDGE_INTERACTION"; ENTITY_EXPOSURE="ENTITY_EXPOSURE"

class PatternStatus(StrEnum): OBSERVED="OBSERVED"; POSSIBLE="POSSIBLE"; REVIEW_REQUIRED="REVIEW_REQUIRED"
class PatternSeverity(StrEnum): INFO="INFO"; LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"; CRITICAL="CRITICAL"

class TraceDirection(StrEnum):
    FORWARD = "forward"
    BACKWARD = "backward"

class CaseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    fraud_type: str = Field(min_length=2, max_length=100)
    priority: str = "MEDIUM"

class WalletCreate(BaseModel):
    address: str = Field(min_length=42, max_length=42)
    chain: Chain = Chain.ETHEREUM
    @field_validator("address")
    @classmethod
    def valid_address(cls, value: str):
        if not value.startswith("0x") or len(value) != 42 or any(c not in "0123456789abcdefABCDEF" for c in value[2:]): raise ValueError("Expected a 20-byte hexadecimal Ethereum address")
        return value

class TransactionCreate(BaseModel):
    tx_hash: str = Field(min_length=66, max_length=66)
    chain: Chain = Chain.ETHEREUM
    @field_validator("tx_hash")
    @classmethod
    def valid_hash(cls, value: str):
        if not value.startswith("0x") or len(value) != 66 or any(c not in "0123456789abcdefABCDEF" for c in value[2:]): raise ValueError("Expected a 32-byte hexadecimal transaction hash")
        return value

class TraceRequest(BaseModel):
    address: str = Field(min_length=42, max_length=42)
    chain: Chain = Chain.ETHEREUM
    direction: TraceDirection = TraceDirection.FORWARD
    max_hops: int = Field(default=2, ge=0, le=6)
    max_nodes: int = Field(default=100, ge=1, le=1000)
    max_edges: int = Field(default=2000, ge=1, le=5000)
    max_transactions: int = Field(default=500, ge=1, le=5000)
    max_duration: int = Field(default=60, ge=1, le=300)
    start_time: datetime | None = None
    end_time: datetime | None = None
    asset_filter: str | None = None
    min_transfer_value: float = Field(default=0, ge=0)
    @field_validator("address")
    @classmethod
    def valid_address(cls, value: str):
        if not value.startswith("0x") or len(value) != 42 or any(c not in "0123456789abcdefABCDEF" for c in value[2:]): raise ValueError("Expected a 20-byte hexadecimal Ethereum address")
        return value

class Transfer(BaseModel):
    tx_hash: str; chain: Chain; block_number: int | None = None; timestamp: datetime | None = None
    source: str; destination: str; asset: str; amount: str; value_native: float | None = None; provider: str
    transfer_type: str = "native"; contract_address: str | None = None; token_id: str | None = None
    decimals: int | None = None; raw_reference: dict = {}

class TransactionDetails(BaseModel):
    tx_hash: str; chain: Chain; block_number: int | None = None; timestamp: datetime | None = None
    status: str = "UNKNOWN"; from_address: str = ""; to_address: str = ""
    native_value: str = "0"; fee: str | None = None; nonce: int | None = None
    gas_limit: int | None = None; gas_price: str | None = None; raw_reference: dict = {}

class TransactionReceipt(BaseModel):
    tx_hash: str; chain: Chain; status: str = "UNKNOWN"; block_number: int | None = None
    gas_used: int | None = None; effective_gas_price: str | None = None; raw_reference: dict = {}

class BlockHeader(BaseModel):
    chain: Chain; block_number: int; block_hash: str | None = None
    timestamp: datetime | None = None; parent_hash: str | None = None; raw_reference: dict = {}

class TransactionRecord(BaseModel):
    transaction_id: str; tx_hash: str; chain: Chain; block_number: int | None = None
    timestamp: datetime | None = None; status: str = "OBSERVED"; from_address: str
    to_address: str; native_value: float | None = None; fee: float | None = None
    raw_reference: dict = {}

class PersistedGraphEdge(BaseModel):
    edge_id: str; case_id: str; transaction_id: str; source_wallet: str
    destination_wallet: str; asset: str; amount: str; timestamp: datetime | None = None; hop: int

class RiskSignal(BaseModel):
    signal_id: str; type: str; severity: str; confidence: float; description: str
    supporting_transaction_hashes: list[str] = []; supporting_addresses: list[str] = []

class Evidence(BaseModel):
    evidence_id: str; case_id: str; type: str; chain: Chain; tx_hash: str | None = None
    source: str; captured_at: datetime; metadata: dict = {}

class TraceLimits(BaseModel):
    max_hops: int; max_nodes: int; max_edges: int; max_transactions: int; max_duration: int

class TraceMetrics(BaseModel):
    node_count: int = 0; edge_count: int = 0; unique_wallet_count: int = 0
    contract_count: int = 0; inbound_edge_count: int = 0; outbound_edge_count: int = 0
    maximum_hop: int = 0; path_count: int = 0; unique_transaction_count: int = 0; unique_asset_count: int = 0

class GraphNode(BaseModel):
    id: str; address: str; depth: int = 0; chain: Chain = Chain.ETHEREUM
    node_type: str = "WALLET"; first_seen: datetime | None = None; last_seen: datetime | None = None
    transaction_count: int = 0; metadata: dict = {}

class GraphEdge(BaseModel):
    source: str; target: str; transfer: Transfer; edge_id: str = ""; hop: int = 0
    asset_type: str = "native"; transaction_hash: str = ""; evidence_id: str | None = None

class TransactionPath(BaseModel):
    path_id: str; node_ids: list[str]; edges: list[GraphEdge]

class FundFlow(BaseModel):
    flow_id: str; asset: str; edges: list[GraphEdge]; initial_amount: str
    final_amount: str; hop_count: int; elapsed_seconds: float | None = None
class TraceResult(BaseModel):
    case_id: str; root_address: str; mode: DataMode; provider: str; nodes: list[GraphNode]
    edges: list[GraphEdge]; signals: list[RiskSignal]; evidence: list[Evidence]; limitations: list[str] = []
    trace_id: str = ""; status: str = "COMPLETED"; direction: TraceDirection = TraceDirection.FORWARD
    limits: TraceLimits | None = None; metrics: TraceMetrics = TraceMetrics()
    paths: list[TransactionPath] = []; flows: list[FundFlow] = []

class InvestigationCase(BaseModel):
    case_id: str; title: str; fraud_type: str; priority: str; status: str
    created_at: datetime; updated_at: datetime; wallets: list[WalletCreate] = []; transactions: list[TransactionCreate] = []; latest_trace: TraceResult | None = None

class ProviderCapability(BaseModel): name: str; status: CapabilityStatus; mode: DataMode | None = None; note: str

class Entity(BaseModel):
    entity_id:str; name:str; entity_type:EntityType; legal_name:str|None=None; jurisdiction:str|None=None; website:str|None=None; metadata:dict={}
class AttributionSource(BaseModel):
    source_id:str; name:str; source_type:str; publisher:str|None=None; reference:str; reliability_level:ConfidenceLevel=ConfidenceLevel.UNKNOWN; description:str|None=None
class AddressAttribution(BaseModel):
    attribution_id:str; chain:Chain; address:str; entity_id:str; role:AttributionRole; confidence:ConfidenceLevel; source_id:str; source_reference:str; evidence_id:str|None=None; first_seen:datetime|None=None; last_verified:datetime|None=None; metadata:dict={}
class AttributionCandidate(BaseModel):
    entity:Entity; attributions:list[AddressAttribution]; confidence:ConfidenceLevel; supporting_sources:list[AttributionSource]; conflicts:list[AddressAttribution]=[]; explanation:str
class ResolvedAttribution(BaseModel):
    chain:Chain; address:str; candidates:list[AttributionCandidate]; selected_entity_id:str|None=None; conflict:bool=False; explanation:str
class NearestEntityResult(BaseModel):
    entity:Entity; address:str; chain:Chain; hop_distance:int; path:TransactionPath; confidence:ConfidenceLevel; role:AttributionRole; supporting_attributions:list[AddressAttribution]; supporting_sources:list[AttributionSource]; evidence:list[Evidence]; explanation:str

class PatternDetectionConfig(BaseModel):
    rapid_hop_minimum_hops: int = Field(default=3, ge=2, le=20)
    rapid_hop_max_interhop_seconds: int = Field(default=600, ge=1, le=86400)
    rapid_hop_minimum_value_retention: float = Field(default=0, ge=0, le=1)
    fan_out_minimum_destinations: int = Field(default=3, ge=2, le=100)
    fan_in_minimum_sources: int = Field(default=3, ge=2, le=100)
    fan_time_window_seconds: int = Field(default=900, ge=1, le=604800)
    fan_value_threshold: float = Field(default=0, ge=0)
    peel_chain_minimum_hops: int = Field(default=2, ge=1, le=20)
    peel_chain_minimum_retention_ratio: float = Field(default=0.01, ge=0, le=1)
    peel_chain_maximum_retention_ratio: float = Field(default=0.5, ge=0, le=1)
    burst_minimum_transactions: int = Field(default=10, ge=2, le=10000)
    burst_window_seconds: int = Field(default=900, ge=1, le=604800)
    dormant_inactivity_seconds: int = Field(default=15552000, ge=1, le=315360000)
    dormant_activity_window_seconds: int = Field(default=1800, ge=1, le=604800)
    dormant_minimum_activity_count: int = Field(default=3, ge=2, le=10000)

class PatternObservation(BaseModel):
    pattern_id: str
    case_id: str
    trace_id: str
    pattern_type: PatternType
    status: PatternStatus = PatternStatus.OBSERVED
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    severity: PatternSeverity = PatternSeverity.INFO
    description: str
    explanation: str
    observed_at: datetime
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    affected_nodes: list[str] = []
    affected_edges: list[str] = []
    transaction_hashes: list[str] = []
    evidence_ids: list[str] = []
    metadata: dict = {}
    fingerprint: str = ""

class PatternAnalyzeRequest(BaseModel):
    trace_id: str | None = None
    config: PatternDetectionConfig = PatternDetectionConfig()

class PatternSummary(BaseModel):
    total_patterns: int = 0
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0

class RiskBand(StrEnum): LOW="LOW"; GUARDED="GUARDED"; ELEVATED="ELEVATED"; HIGH="HIGH"; CRITICAL="CRITICAL"
class InvestigativePriority(StrEnum): INFORMATIONAL="INFORMATIONAL"; REVIEW="REVIEW"; PRIORITY="PRIORITY"; URGENT="URGENT"; CRITICAL="CRITICAL"
class WatchStatus(StrEnum): NOT_MONITORED="NOT_MONITORED"; MONITORED="MONITORED"; PAUSED="PAUSED"; CLOSED="CLOSED"
class RiskAlertStatus(StrEnum): NEW="NEW"; ACKNOWLEDGED="ACKNOWLEDGED"; DISMISSED="DISMISSED"; ESCALATED="ESCALATED"

class RiskSubject(BaseModel):
    subject_id: str
    case_id: str
    chain: Chain
    address: str
    subject_type: str = "WALLET"

class RiskFactorDefinition(BaseModel):
    id: str
    name: str
    category: str
    default_weight: float = Field(ge=0)
    max_contribution: float = Field(ge=0)
    enabled: bool = True
    explanation_template: str
    required_evidence_type: str = "TRANSACTION"

class RiskBandThresholds(BaseModel):
    guarded_min: float = Field(default=20, ge=0, le=100)
    elevated_min: float = Field(default=40, ge=0, le=100)
    high_min: float = Field(default=60, ge=0, le=100)
    critical_min: float = Field(default=80, ge=0, le=100)

class RiskScoringConfig(BaseModel):
    version: str = "phase6-default-v1"
    factors: list[RiskFactorDefinition] = []
    thresholds: RiskBandThresholds = RiskBandThresholds()

class RiskFactor(BaseModel):
    factor_id: str
    definition_id: str
    name: str
    category: str
    contribution: float = Field(ge=0)
    max_contribution: float = Field(ge=0)
    explanation: str
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    pattern_ids: list[str] = []
    entity_ids: list[str] = []
    transaction_hashes: list[str] = []
    evidence_ids: list[str] = []
    metadata: dict = {}

class RiskDelta(BaseModel):
    previous_score: float | None = None
    current_score: float
    delta: float
    new_factors: list[str] = []
    removed_factors: list[str] = []
    changed_factors: list[str] = []

class RiskAssessment(BaseModel):
    assessment_id: str
    case_id: str
    trace_id: str
    subject: RiskSubject
    version: int = Field(ge=1)
    score: float = Field(ge=0, le=100)
    band: RiskBand
    priority: InvestigativePriority
    priority_reason: str
    watch_status: WatchStatus = WatchStatus.NOT_MONITORED
    factors: list[RiskFactor] = []
    delta: RiskDelta | None = None
    calculation_version: str
    calculated_at: datetime
    evidence_ids: list[str] = []
    pattern_ids: list[str] = []
    entity_ids: list[str] = []
    explanation: str
    previous_assessment_id: str | None = None

class RiskAssessRequest(BaseModel):
    trace_id: str | None = None
    subject_address: str | None = None
    config: RiskScoringConfig = RiskScoringConfig()

class RiskAlertCandidate(BaseModel):
    candidate_id: str
    case_id: str
    subject_id: str
    assessment_id: str
    trigger: str
    severity: RiskBand
    risk_delta: float
    pattern_ids: list[str] = []
    evidence_ids: list[str] = []
    created_at: datetime
    status: RiskAlertStatus = RiskAlertStatus.NEW

class AuditEvent(BaseModel):
    event_id: str
    case_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    actor_id: str | None = None
    occurred_at: datetime
    metadata: dict = {}

class RealtimeEventType(StrEnum): ADDRESS_ACTIVITY="ADDRESS_ACTIVITY"; REORG="REORG"
class RealtimeProcessingStatus(StrEnum): RECEIVED="RECEIVED"; VALIDATED="VALIDATED"; NORMALIZED="NORMALIZED"; APPLIED="APPLIED"; DUPLICATE="DUPLICATE"; REJECTED="REJECTED"; FAILED="FAILED"; RETRY_PENDING="RETRY_PENDING"
class ConfirmationState(StrEnum): OBSERVED="OBSERVED"; CONFIRMED="CONFIRMED"; REORGED="REORGED"
class WatchTargetStatus(StrEnum): ACTIVE="ACTIVE"; PAUSED="PAUSED"; STOPPED="STOPPED"; ERROR="ERROR"
class WatchExpansionPolicy(StrEnum): MANUAL="MANUAL"; CASE_DEFAULT="CASE_DEFAULT"; HIGH_CONFIDENCE="HIGH_CONFIDENCE"; RISK_TRIGGERED="RISK_TRIGGERED"
class AlertStatus(StrEnum): NEW="NEW"; ACKNOWLEDGED="ACKNOWLEDGED"; DISMISSED="DISMISSED"; ESCALATED="ESCALATED"

class RealtimeEvent(BaseModel):
    event_id: str
    provider: str
    provider_event_id: str | None = None
    chain: Chain
    event_type: RealtimeEventType = RealtimeEventType.ADDRESS_ACTIVITY
    received_at: datetime
    observed_at: datetime | None = None
    block_number: int | None = None
    block_hash: str | None = None
    transaction_hash: str
    transfer_index: int | None = None
    from_address: str
    to_address: str
    asset: str
    amount: str
    contract_address: str | None = None
    token_id: str | None = None
    raw_provider_reference: dict = {}
    processing_status: RealtimeProcessingStatus = RealtimeProcessingStatus.RECEIVED
    confirmation_state: ConfirmationState = ConfirmationState.OBSERVED
    removed: bool = False
    error: str | None = None

class WatchCreate(BaseModel):
    address: str = Field(min_length=42,max_length=42)
    chain: Chain = Chain.ETHEREUM
    source: str = "INVESTIGATOR"
    expansion_policy: WatchExpansionPolicy = WatchExpansionPolicy.MANUAL
    max_hops: int = Field(default=2,ge=0,le=6)
    max_new_nodes_per_event: int = Field(default=25,ge=1,le=500)
    max_new_edges_per_event: int = Field(default=100,ge=1,le=2000)
    max_value: float = Field(default=0,ge=0)
    allowed_assets: list[str] = []

class WatchTarget(BaseModel):
    watch_id: str
    case_id: str
    address: str
    chain: Chain
    source: str
    created_at: datetime
    status: WatchTargetStatus
    provider: str
    subscription_id: str | None = None
    last_event_at: datetime | None = None
    last_processed_block: int | None = None
    last_processed_event: str | None = None
    expansion_policy: WatchExpansionPolicy = WatchExpansionPolicy.MANUAL
    max_hops: int = 2
    max_new_nodes_per_event: int = 25
    max_new_edges_per_event: int = 100
    max_value: float = 0
    allowed_assets: list[str] = []
    error: str | None = None

class TimelineEvent(BaseModel):
    event_id: str
    case_id: str
    timestamp: datetime
    event_type: str
    summary: str
    source: str
    evidence_ids: list[str] = []
    metadata: dict = {}

class InvestigationChangeSet(BaseModel):
    change_set_id: str
    case_id: str
    event_id: str
    created_at: datetime
    before: dict = {}
    after: dict = {}
    changes: dict = {}

class Alert(BaseModel):
    alert_id: str
    case_id: str
    subject_id: str
    alert_type: str
    title: str
    explanation: str
    severity: RiskBand
    status: AlertStatus = AlertStatus.NEW
    risk_delta: float = 0
    pattern_ids: list[str] = []
    evidence_ids: list[str] = []
    created_at: datetime

class RealtimeApplicationResult(BaseModel):
    event: RealtimeEvent
    case_id: str
    watch_id: str
    transaction_id: str | None = None
    evidence_id: str | None = None
    graph_edge_id: str | None = None
    new_wallet: bool = False
    duplicate: bool = False
