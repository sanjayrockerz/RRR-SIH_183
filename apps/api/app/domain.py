from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field, field_validator, model_validator

class CapabilityStatus(StrEnum):
    SUPPORTED = "SUPPORTED"; UNSUPPORTED = "UNSUPPORTED"; SIMULATED = "SIMULATED"; NOT_CONFIGURED = "NOT_CONFIGURED"; UNAVAILABLE = "UNAVAILABLE"; RATE_LIMITED = "RATE_LIMITED"

class DataMode(StrEnum):
    HISTORICAL = "HISTORICAL"; POLLING = "POLLING"; WEBHOOK = "WEBHOOK"; SUBSCRIPTION = "SUBSCRIPTION"; SIMULATED = "SIMULATED"; DEVELOPMENT_FIXTURE = "DEVELOPMENT_FIXTURE"

class Chain(StrEnum): ETHEREUM = "ethereum"; TRON = "tron"

def normalize_address(chain: Chain, address: str) -> str:
    """Normalize address representation without destroying chain semantics."""
    return address.lower() if chain == Chain.ETHEREUM else address

class EntityType(StrEnum):
    VASP="VASP"; EXCHANGE="EXCHANGE"; CUSTODIAL_SERVICE="CUSTODIAL_SERVICE"; NON_CUSTODIAL_WALLET="NON_CUSTODIAL_WALLET"; SERVICE="SERVICE"; MIXER="MIXER"; BRIDGE="BRIDGE"; CONTRACT="CONTRACT"; SCAM_INFRASTRUCTURE="SCAM_INFRASTRUCTURE"; PROTOCOL="PROTOCOL"; UNKNOWN="UNKNOWN"
class AttributionRole(StrEnum):
    DEPOSIT="DEPOSIT"; HOT_WALLET="HOT_WALLET"; COLD_WALLET="COLD_WALLET"; TREASURY="TREASURY"; CONTRACT="CONTRACT"; SERVICE="SERVICE"; UNKNOWN="UNKNOWN"
    MIXER_CONTRACT="MIXER_CONTRACT"; BRIDGE_DEPOSIT="BRIDGE_DEPOSIT"; DEPOSIT_ADDRESS="DEPOSIT_ADDRESS"; WITHDRAWAL="WITHDRAWAL"; BRIDGE_WITHDRAWAL="BRIDGE_WITHDRAWAL"
class ConfidenceLevel(StrEnum):
    UNKNOWN="UNKNOWN"; LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"; CONFIRMED="CONFIRMED"

class PatternType(StrEnum):
    RAPID_HOP="RAPID_HOP"; FAN_OUT="FAN_OUT"; FAN_IN="FAN_IN"; PEEL_CHAIN="PEEL_CHAIN"
    CONSOLIDATION="CONSOLIDATION"; BURST_ACTIVITY="BURST_ACTIVITY"; DORMANT_ACTIVATION="DORMANT_ACTIVATION"
    MIXER_INTERACTION="MIXER_INTERACTION"; BRIDGE_INTERACTION="BRIDGE_INTERACTION"; ENTITY_EXPOSURE="ENTITY_EXPOSURE"
    CROSS_CHAIN_HOP="CROSS_CHAIN_HOP"; BRIDGE_HOP="BRIDGE_HOP"; RAPID_CROSS_CHAIN_MOVEMENT="RAPID_CROSS_CHAIN_MOVEMENT"
    CROSS_CHAIN_FRAGMENTATION="CROSS_CHAIN_FRAGMENTATION"; CROSS_CHAIN_CONSOLIDATION="CROSS_CHAIN_CONSOLIDATION"
    MULTI_CHAIN_PEEL_CHAIN="MULTI_CHAIN_PEEL_CHAIN"; CHAIN_SWITCH_AFTER_RISK_SIGNAL="CHAIN_SWITCH_AFTER_RISK_SIGNAL"; BRIDGE_TO_ENTITY_EXPOSURE="BRIDGE_TO_ENTITY_EXPOSURE"

class PatternStatus(StrEnum): OBSERVED="OBSERVED"; POSSIBLE="POSSIBLE"; REVIEW_REQUIRED="REVIEW_REQUIRED"
class PatternSeverity(StrEnum): INFO="INFO"; LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"; CRITICAL="CRITICAL"

class TraceDirection(StrEnum):
    FORWARD = "forward"
    BACKWARD = "backward"

class CaseWorkflowStage(StrEnum):
    NEW="NEW"; INTAKE_COMPLETE="INTAKE_COMPLETE"; DATA_ACQUISITION="DATA_ACQUISITION"; TRACE_ANALYZED="TRACE_ANALYZED"; PATTERNS_ANALYZED="PATTERNS_ANALYZED"; RISK_ASSESSED="RISK_ASSESSED"; WATCHING="WATCHING"; ALERTED="ALERTED"; UNDER_REVIEW="UNDER_REVIEW"; REPORT_READY="REPORT_READY"; CLOSED="CLOSED"

class CaseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    fraud_type: str = Field(min_length=2, max_length=100)
    priority: str = "MEDIUM"
    external_case_reference: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    created_by: str | None = Field(default=None, max_length=200)

class CasePatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    fraud_type: str | None = Field(default=None, min_length=2, max_length=100)
    priority: str | None = None
    description: str | None = Field(default=None, max_length=5000)
    external_case_reference: str | None = Field(default=None, max_length=200)

class CaseListItem(BaseModel):
    case_id: str
    title: str
    fraud_type: str
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    wallet_count: int = 0
    transaction_count: int = 0
    external_case_reference: str | None = None
    wallet_address: str | None = None
    risk_band: str | None = None
    workflow_stage: CaseWorkflowStage = CaseWorkflowStage.NEW

class DashboardSummary(BaseModel):
    active_cases: int = 0
    wallets_under_review: int = 0
    high_priority_alerts: int = 0
    attributed_entities: int = 0
    observed_transactions: int = 0
    active_watches: int = 0
    last_activity_at: datetime | None = None
    investigations_today: int = 0
    wallets_under_investigation: int = 0
    transactions_analyzed: int = 0
    graph_nodes: int = 0
    graph_edges: int = 0
    open_alerts: int = 0
    critical_cases: int = 0
    latest_blockchain_event: dict | None = None
    latest_graph_mutation: dict | None = None
    latest_pattern: dict | None = None
    latest_risk_change: dict | None = None
    latest_alert: dict | None = None

class CaseSummarySnapshot(BaseModel):
    case_id: str
    status: str
    workflow_stage: CaseWorkflowStage
    wallets: int = 0
    transactions: int = 0
    graph_nodes: int = 0
    graph_edges: int = 0
    patterns: int = 0
    alerts: int = 0
    evidence: int = 0
    realtime_events: int = 0
    active_watches: int = 0
    vasp_exposure: dict = {}
    risk: 'RiskAssessment | None' = None
    generated_at: datetime

class OperationalStageState(BaseModel):
    stage: str
    status: str = "PENDING"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    records_produced: int = 0
    provider: str | None = None
    mode: str | None = None
    error: str | None = None
    evidence_ids: list[str] = []

class InvestigationOperationalState(BaseModel):
    case: 'InvestigationCase'
    summary: CaseSummarySnapshot
    stages: list[OperationalStageState] = []
    workflow_events: list[dict] = []
    transactions: list['CaseTransactionView'] = []
    entities: list['Entity'] = []
    attributions: list['NearestEntityResult'] = []
    patterns: list['PatternObservation'] = []
    risk: 'RiskAssessment | None' = None
    watches: list['WatchTarget'] = []
    alerts: list['Alert'] = []
    evidence: list['Evidence'] = []
    reports: list['InvestigationReport'] = []
    graph_backend: str = "PostgreSQL"
    generated_at: datetime

class InvestigationRunRequest(BaseModel):
    address: str | None = Field(default=None, min_length=34, max_length=42)
    chain: Chain = Chain.ETHEREUM
    direction: TraceDirection = TraceDirection.FORWARD
    max_hops: int = Field(default=3, ge=0, le=6)
    max_nodes: int = Field(default=100, ge=1, le=1000)
    max_edges: int = Field(default=500, ge=1, le=5000)
    max_transactions: int = Field(default=500, ge=1, le=5000)
    start_watch: bool = True
    create_report: bool = False
    @field_validator("address")
    @classmethod
    def valid_optional_address(cls, value: str | None):
        if value is None or value == "":
            return value
        return TraceRequest(address=value).address

class DatabaseStatus(BaseModel):
    status: str
    migration_status: str
    detail: str | None = None
    checked_at: datetime

class WalletCreate(BaseModel):
    address: str = Field(min_length=34, max_length=42)
    chain: Chain = Chain.ETHEREUM
    @field_validator("address")
    @classmethod
    def valid_address(cls, value: str):
        if value.startswith("0x") and len(value) == 42 and all(c in "0123456789abcdefABCDEF" for c in value[2:]): return value
        if value.startswith("T") and len(value) == 34 and all(c in "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz" for c in value): return value
        raise ValueError("Expected a valid Ethereum or Tron address")

class WalletIntelligence(BaseModel):
    wallet_id: str
    chain: Chain
    address: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    transaction_count: int = 0
    inbound_count: int = 0
    outbound_count: int = 0
    assets: list[str] = []
    case_count: int = 0
    related_case_ids: list[str] = []
    evidence_count: int = 0
    observation_status: str = "PERSISTED_OBSERVATIONS"

class TransactionCreate(BaseModel):
    tx_hash: str = Field(min_length=64, max_length=66)
    chain: Chain = Chain.ETHEREUM
    @field_validator("tx_hash")
    @classmethod
    def valid_hash(cls, value: str):
        if (value.startswith("0x") and len(value) == 66 and all(c in "0123456789abcdefABCDEF" for c in value[2:])) or (len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value)): return value
        raise ValueError("Expected a 32-byte hexadecimal transaction hash")

class TraceRequest(BaseModel):
    address: str = Field(min_length=34, max_length=42)
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
        if (value.startswith("0x") and len(value) == 42 and all(c in "0123456789abcdefABCDEF" for c in value[2:])) or (value.startswith("T") and len(value) == 34 and all(c in "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz" for c in value)): return value
        raise ValueError("Expected a valid Ethereum or Tron address")

class SyntheticCaseRequest(BaseModel):
    """Development-only request. Generated observations still traverse RealtimeService."""
    event_count: int = Field(default=50, ge=1, le=1000)
    scenario: str = Field(default="MULTI_STAGE_FRAUD", min_length=2, max_length=80)
    scenario_seed: str = Field(default="rrr-synthetic-case", min_length=1, max_length=200)

class MobileTraceRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=64)
    address: str = Field(min_length=34, max_length=42)
    chain: Chain = Chain.ETHEREUM
    direction: TraceDirection = TraceDirection.FORWARD
    max_hops: int = Field(default=3, ge=0, le=6)
    max_nodes: int = Field(default=100, ge=1, le=1000)
    max_edges: int = Field(default=2000, ge=1, le=5000)
    max_transactions: int = Field(default=500, ge=1, le=5000)
    @field_validator("address")
    @classmethod
    def valid_mobile_address(cls, value: str):
        return TraceRequest(address=value).address

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

class CaseTransactionView(BaseModel):
    """Case-scoped ledger record assembled from canonical transaction, transfer and evidence rows."""
    case_id: str
    transaction_id: str
    tx_hash: str
    chain: Chain
    block_number: int | None = None
    timestamp: datetime | None = None
    status: str = "UNKNOWN"
    from_address: str
    to_address: str
    asset: str
    amount: str
    transfer_type: str = "native"
    contract_address: str | None = None
    token_id: str | None = None
    decimals: int | None = None
    provider: str
    observed_at: datetime | None = None
    evidence_ids: list[str] = []
    risk_score: float = 0
    risk_band: str = "LOW"
    risk_factors: list[dict] = []
    pattern_observations: list[dict] = []
    entity_exposure: list[dict] = []

class PersistedGraphEdge(BaseModel):
    edge_id: str; case_id: str; transaction_id: str; source_wallet: str
    destination_wallet: str; asset: str; amount: str; timestamp: datetime | None = None; hop: int

class RiskSignal(BaseModel):
    signal_id: str; type: str; severity: str; confidence: float; description: str
    supporting_transaction_hashes: list[str] = []; supporting_addresses: list[str] = []

class Evidence(BaseModel):
    evidence_id: str; case_id: str; type: str; chain: Chain; tx_hash: str | None = None
    source: str; captured_at: datetime; metadata: dict = {}
    content_hash: str | None = None
    integrity_status: str = "UNVERIFIED"

class EvidenceChainEvent(BaseModel):
    event_id: str
    evidence_id: str
    case_id: str
    event_type: str
    actor_id: str | None = None
    occurred_at: datetime
    previous_hash: str | None = None
    event_hash: str
    metadata: dict = {}

class EvidenceManifest(BaseModel):
    manifest_id: str
    case_id: str
    algorithm: str = "SHA-256"
    content_hash: str
    evidence_ids: list[str] = []
    evidence_count: int = 0
    created_at: datetime
    created_by: str | None = None

class EvidenceLedgerEntry(BaseModel):
    evidence: Evidence
    chain_of_custody: list[EvidenceChainEvent] = []
    manifest_ids: list[str] = []

class EvidenceManifestRequest(BaseModel):
    evidence_ids: list[str] = Field(default_factory=list, max_length=10000)
    created_by: str | None = Field(default=None, max_length=200)

class ReportType(StrEnum):
    INVESTIGATION_SUMMARY = "INVESTIGATION_SUMMARY"
    FUND_FLOW = "FUND_FLOW"
    EVIDENCE = "EVIDENCE"

class ReportCreateRequest(BaseModel):
    report_type: ReportType = ReportType.INVESTIGATION_SUMMARY
    trace_id: str | None = None
    created_by: str | None = Field(default=None, max_length=200)

class InvestigationReport(BaseModel):
    report_id: str
    case_id: str
    report_type: ReportType
    trace_id: str | None = None
    title: str
    content: str
    evidence_ids: list[str] = []
    pattern_ids: list[str] = []
    assessment_id: str | None = None
    content_hash: str
    created_at: datetime
    created_by: str | None = None

class CaseLink(BaseModel):
    link_id: str
    case_id: str
    related_case_id: str
    relationship_type: str
    shared_wallets: list[dict] = []
    shared_transactions: list[dict] = []
    confidence_level: ConfidenceLevel = ConfidenceLevel.CONFIRMED
    explanation: str
    created_at: datetime

class TraceLimits(BaseModel):
    max_hops: int; max_nodes: int; max_edges: int; max_transactions: int; max_duration: int

class TraceMetrics(BaseModel):
    node_count: int = 0; edge_count: int = 0; unique_wallet_count: int = 0
    contract_count: int = 0; inbound_edge_count: int = 0; outbound_edge_count: int = 0
    maximum_hop: int = 0; path_count: int = 0; unique_transaction_count: int = 0; unique_asset_count: int = 0

class AcquisitionStatistics(BaseModel):
    discovered: int = 0
    normalized: int = 0
    persisted: int = 0
    duplicates: int = 0
    failed: int = 0
    skipped: int = 0
    provider: str = ""
    mode: DataMode = DataMode.HISTORICAL
    retrieved_at: datetime | None = None

class GraphNode(BaseModel):
    id: str; address: str; depth: int = 0; chain: Chain = Chain.ETHEREUM
    node_type: str = "WALLET"; first_seen: datetime | None = None; last_seen: datetime | None = None
    transaction_count: int = 0; metadata: dict = {}

class GraphEdge(BaseModel):
    source: str; target: str; transfer: Transfer; edge_id: str = ""; hop: int = 0
    asset_type: str = "native"; transaction_hash: str = ""; evidence_id: str | None = None
    from_address: str = Field(default="", alias="from")
    to_address: str = Field(default="", alias="to")
    asset: str = ""
    amount: str = ""
    timestamp: datetime | None = None
    block_number: int | None = None
    direction: str = "forward"
    model_config = {
        "populate_by_name": True
    }
    @model_validator(mode='after')
    def populate_fields(self):
        if self.transfer:
            self.from_address = self.transfer.source
            self.to_address = self.transfer.destination
            self.asset = self.transfer.asset
            self.amount = self.transfer.amount
            self.timestamp = self.transfer.timestamp
            self.block_number = self.transfer.block_number
            self.transaction_hash = self.transfer.tx_hash
        return self

class GraphLayout(BaseModel):
    case_id: str
    node_positions: dict[str, dict[str, float | bool]] = {}
    viewport: dict[str, float] = {}
    updated_at: datetime | None = None

class GraphLayoutUpdate(BaseModel):
    node_positions: dict[str, dict[str, float | bool]] = {}
    viewport: dict[str, float] = {}

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
    paths: list[TransactionPath] = []; flows: list[FundFlow] = []; acquisition: AcquisitionStatistics = AcquisitionStatistics()

class InvestigationCase(BaseModel):
    case_id: str; title: str; fraud_type: str; priority: str; status: str
    created_at: datetime; updated_at: datetime; wallets: list[WalletCreate] = []; transactions: list[TransactionCreate] = []; latest_trace: TraceResult | None = None
    external_case_reference: str | None = None
    description: str | None = None
    created_by: str | None = None
    closed_at: datetime | None = None
    workflow_stage: CaseWorkflowStage = CaseWorkflowStage.NEW

class ProviderCapability(BaseModel): name: str; status: CapabilityStatus; mode: DataMode | None = None; note: str

class ProviderOperationalStatus(BaseModel):
    provider: str
    chains: list[Chain] = []
    status: CapabilityStatus
    capabilities: list[ProviderCapability] = []
    checked_at: datetime
    detail: str

class Entity(BaseModel):
    entity_id:str; name:str; entity_type:EntityType; legal_name:str|None=None; jurisdiction:str|None=None; website:str|None=None; metadata:dict={}
class AttributionSource(BaseModel):
    source_id:str; name:str; source_type:str; publisher:str|None=None; reference:str; reliability_level:ConfidenceLevel=ConfidenceLevel.UNKNOWN; description:str|None=None
    dataset_version:str|None=None
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
class RealtimeProcessingStatus(StrEnum): RECEIVED="RECEIVED"; VALIDATED="VALIDATED"; NORMALIZED="NORMALIZED"; APPLIED="APPLIED"; DUPLICATE="DUPLICATE"; REJECTED="REJECTED"; FAILED="FAILED"; RETRY_PENDING="RETRY_PENDING"; DEAD_LETTER="DEAD_LETTER"
class ConfirmationState(StrEnum): OBSERVED="OBSERVED"; CONFIRMED="CONFIRMED"; REORGED="REORGED"
class WatchTargetStatus(StrEnum): ACTIVE="ACTIVE"; PAUSED="PAUSED"; STOPPED="STOPPED"; ERROR="ERROR"
class WatchExpansionPolicy(StrEnum): MANUAL="MANUAL"; CASE_DEFAULT="CASE_DEFAULT"; HIGH_CONFIDENCE="HIGH_CONFIDENCE"; RISK_TRIGGERED="RISK_TRIGGERED"
class AlertStatus(StrEnum): NEW="NEW"; ACKNOWLEDGED="ACKNOWLEDGED"; DISMISSED="DISMISSED"; ESCALATED="ESCALATED"

class AlertReviewAction(StrEnum): ACKNOWLEDGE="ACKNOWLEDGE"; DISMISS="DISMISS"; ESCALATE="ESCALATE"

class AlertReviewRequest(BaseModel):
    action: AlertReviewAction
    note: str | None = Field(default=None, max_length=5000)
    actor_id: str | None = Field(default=None, max_length=200)

class AlertReview(BaseModel):
    review_id: str
    alert_id: str
    case_id: str
    from_status: AlertStatus
    to_status: AlertStatus
    action: AlertReviewAction
    note: str | None = None
    actor_id: str | None = None
    created_at: datetime

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
    attempt_count: int = Field(default=0, ge=0)
    next_attempt_at: datetime | None = None
    dead_lettered_at: datetime | None = None

class RealtimeProcessingAttempt(BaseModel):
    attempt_id: str
    event_id: str
    attempt_number: int
    status: RealtimeProcessingStatus
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None

class RealtimeOperationalEvent(BaseModel):
    event: RealtimeEvent
    attempts: list[RealtimeProcessingAttempt] = []
    retryable: bool = False

class WatchCreate(BaseModel):
    address: str = Field(min_length=34,max_length=42)
    chain: Chain = Chain.ETHEREUM
    source: str = "INVESTIGATOR"
    expansion_policy: WatchExpansionPolicy = WatchExpansionPolicy.MANUAL
    max_hops: int = Field(default=2,ge=0,le=6)
    max_new_nodes_per_event: int = Field(default=25,ge=1,le=500)
    max_new_edges_per_event: int = Field(default=100,ge=1,le=2000)
    max_value: float = Field(default=0,ge=0)
    allowed_assets: list[str] = []
    @field_validator("address")
    @classmethod
    def valid_address(cls, value: str):
        if (value.startswith("0x") and len(value) == 42 and all(c in "0123456789abcdefABCDEF" for c in value[2:])) or (value.startswith("T") and len(value) == 34 and all(c in "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz" for c in value)):
            return value
        raise ValueError("Expected a valid Ethereum or Tron address")

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

# Phase F: cyber-intelligence contracts. These records are source-backed and
# deliberately separate from blockchain observations and investigative risk.
class IntelligenceSourceStatus(StrEnum):
    CONFIGURED="CONFIGURED"; NOT_CONFIGURED="NOT_CONFIGURED"; UNAVAILABLE="UNAVAILABLE"
class IndicatorType(StrEnum):
    WALLET="WALLET"; TRANSACTION="TRANSACTION"; CONTRACT="CONTRACT"; DOMAIN="DOMAIN"; OTHER="OTHER"
class ScreeningOutcome(StrEnum):
    DIRECT_MATCH="DIRECT_MATCH"; INDIRECT_MATCH="INDIRECT_MATCH"; NO_MATCH="NO_MATCH"; UNKNOWN="UNKNOWN"; NOT_CONFIGURED="NOT_CONFIGURED"
class IntelligenceConfidence(StrEnum): LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"; UNKNOWN="UNKNOWN"

class IntelligenceSource(BaseModel):
    source_id: str
    name: str
    source_type: str
    publisher: str | None = None
    reference: str
    dataset_version: str
    status: IntelligenceSourceStatus = IntelligenceSourceStatus.CONFIGURED
    retrieved_at: datetime | None = None
    metadata: dict = {}

class ThreatIndicator(BaseModel):
    indicator_id: str
    source_id: str
    indicator_type: IndicatorType
    value: str
    normalized_value: str
    chain: Chain | None = None
    confidence: IntelligenceConfidence = IntelligenceConfidence.UNKNOWN
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    metadata: dict = {}

class SanctionsRecord(BaseModel):
    record_id: str
    source_id: str
    subject_type: IndicatorType
    value: str
    normalized_value: str
    chain: Chain | None = None
    program: str | None = None
    listed_at: datetime | None = None
    revoked_at: datetime | None = None
    confidence: IntelligenceConfidence = IntelligenceConfidence.HIGH
    source_reference: str
    dataset_version: str
    metadata: dict = {}

class ScreeningMatch(BaseModel):
    match_id: str
    record_id: str
    source_id: str
    matched_value: str
    match_type: ScreeningOutcome = ScreeningOutcome.DIRECT_MATCH
    confidence: IntelligenceConfidence = IntelligenceConfidence.UNKNOWN
    explanation: str
    evidence_ids: list[str] = []

class AddressScreeningResult(BaseModel):
    chain: Chain
    address: str
    outcome: ScreeningOutcome
    source_status: IntelligenceSourceStatus
    screened_at: datetime
    matches: list[ScreeningMatch] = []
    explanation: str
    limitation: str | None = None

class ContractSecurityFinding(BaseModel):
    finding_id: str
    chain: Chain
    contract_address: str
    source_id: str
    finding_type: str
    severity: PatternSeverity = PatternSeverity.INFO
    confidence: IntelligenceConfidence = IntelligenceConfidence.UNKNOWN
    description: str
    evidence_ids: list[str] = []
    observed_at: datetime
    metadata: dict = {}

class CyberIntelligenceSummary(BaseModel):
    case_id: str
    screened_addresses: int = 0
    direct_matches: int = 0
    indirect_matches: int = 0
    unknown_results: int = 0
    source_status: IntelligenceSourceStatus
    records: list[AddressScreeningResult] = []

# Phase 8: chain-aware forensic intelligence contracts. These models are kept
# separate from the Phase 0-7 Ethereum graph contracts so existing API payloads
# remain backward compatible while cross-chain identity is explicit.
class ChainCapability(BaseModel):
    chain_id: Chain
    name: str
    family: str
    native_asset: str
    address_format: str
    explorer_base_url: str
    block_time_seconds: float
    finality_model: str
    provider: str
    historical_capability: CapabilityStatus
    realtime_capability: CapabilityStatus
    token_transfer_capability: CapabilityStatus
    bridge_detection_capability: CapabilityStatus
    note: str | None = None

class ChainAddress(BaseModel):
    chain: Chain
    address: str
    @field_validator("address")
    @classmethod
    def valid_chain_address(cls, value: str):
        WalletCreate(address=value).valid_address(value)
        return value

class AssetIdentity(BaseModel):
    chain: Chain
    contract_address: str | None = None
    symbol: str
    decimals: int | None = None
    canonical_asset_id: str
    mapping_source: str
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN

class AssetMapping(BaseModel):
    mapping_id: str
    source: AssetIdentity
    destination: AssetIdentity
    confidence: ConfidenceLevel
    mapping_source: str
    version: str
    evidence_ids: list[str] = []

class BridgeDefinition(BaseModel):
    bridge_id: str
    name: str
    supported_chains: list[Chain]
    deposit_contracts: dict[Chain, list[str]] = {}
    withdrawal_contracts: dict[Chain, list[str]] = {}
    router_contracts: dict[Chain, list[str]] = {}
    token_mappings: list[AssetMapping] = []
    event_signatures: list[str] = []
    confidence_policy: str = "Source-backed contract interaction only"
    source: str
    version: str

class BridgeInteraction(BaseModel):
    interaction_id: str
    bridge_id: str
    bridge_name: str
    interaction_type: str
    source_chain: Chain
    destination_chain: Chain | None = None
    transaction_hash: str
    bridge_contract: str
    source_address: str
    recipient: str | None = None
    asset: str
    amount: str
    timestamp: datetime | None = None
    message_id: str | None = None
    nonce: str | None = None
    evidence_ids: list[str] = []
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    source: str
    explanation: str
    raw_reference: dict = {}

class CrossChainLink(BaseModel):
    link_id: str
    source: ChainAddress
    destination: ChainAddress | None = None
    source_transaction_hash: str
    destination_transaction_hash: str
    bridge_id: str
    correlation_id: str
    correlation_level: str
    confidence_score: float = Field(ge=0, le=1)
    confidence_band: ConfidenceLevel
    evidence_count: int = 0
    correlation_reasons: list[str] = []
    evidence_ids: list[str] = []
    provenance_source: str
    explanation: str
    observed_or_inferred: str = "INFERRED"
    asset: str | None = None
    amount: str | None = None
    timestamp: datetime | None = None
    bridge_protocol: str | None = None
    created_at: datetime

class CrossChainTransfer(BaseModel):
    """Canonical, evidence-backed bridge hop between two blockchain networks."""
    source_chain: Chain
    destination_chain: Chain
    source_tx: str
    destination_tx: str
    bridge_protocol: str
    asset: str
    amount: str
    timestamp: datetime | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    evidence_ids: list[str] = []
    correlation_id: str
    observed_or_inferred: str = "INFERRED"

class CrossChainPrimaryPath(BaseModel):
    status: str = "UNKNOWN"
    node_ids: list[str] = []
    edge_ids: list[str] = []
    chain_labels: list[str] = []
    terminal_address: str | None = None
    terminal_entity_id: str | None = None
    terminal_entity_name: str = "UNKNOWN / UNATTRIBUTED DESTINATION"
    terminal_entity_type: str = "UNKNOWN"
    attribution: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    hops: int = 0
    why: str = "No verified cross-chain primary path is available."
    evidence_ids: list[str] = []
    transaction_hashes: list[str] = []

class CrossChainEvidence(BaseModel):
    evidence_id: str
    case_id: str
    evidence_type: str
    source_chain: Chain
    destination_chain: Chain | None = None
    source_transaction_hash: str | None = None
    destination_transaction_hash: str | None = None
    source: str
    captured_at: datetime
    provenance: str
    observed_or_inferred: str
    metadata: dict = {}

class CrossChainNode(BaseModel):
    node_id: str
    chain: Chain
    address: str
    node_type: str = "WALLET"
    metadata: dict = {}

class CrossChainEdge(BaseModel):
    edge_id: str
    edge_type: str
    source_node: str
    destination_node: str
    chain: Chain | None = None
    destination_chain: Chain | None = None
    transaction_hash: str | None = None
    destination_transaction_hash: str | None = None
    asset: str | None = None
    amount: str | None = None
    timestamp: datetime | None = None
    bridge_id: str | None = None
    link_id: str | None = None
    confidence_band: ConfidenceLevel | None = None
    evidence_ids: list[str] = []
    observed_or_inferred: str = "OBSERVED"
    metadata: dict = {}

class CrossChainPath(BaseModel):
    path_id: str
    node_ids: list[str]
    edge_ids: list[str]
    chains: list[Chain]
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN

class CrossChainTrace(BaseModel):
    trace_id: str
    case_id: str
    root: ChainAddress
    chains_visited: list[Chain] = []
    cross_chain_hops: int = 0
    cross_chain_links: list[CrossChainLink] = []
    cross_chain_transfers: list[CrossChainTransfer] = []
    primary_path: CrossChainPrimaryPath | None = None
    nodes: list[CrossChainNode] = []
    edges: list[CrossChainEdge] = []
    paths: list[CrossChainPath] = []
    status: str = "COMPLETED"
    limitations: list[str] = []
    max_hops: int = 8
    max_cross_chain_hops: int = 2
    max_nodes: int = 500
    max_edges: int = 2000
    max_bridge_interactions: int = 50
    max_transactions: int = 500
    provider_states: list[ProviderCapability] = []

class CrossChainObservationCreate(BaseModel):
    transfer: Transfer
    mode: DataMode = DataMode.SIMULATED
    bridge_contract: str | None = None
    message_id: str | None = None
    nonce: str | None = None
    destination_chain: Chain | None = None
    destination_address: str | None = None
    source: str = "INVESTIGATOR"

class CrossChainAnalyzeRequest(BaseModel):
    chains: list[Chain] = [Chain.ETHEREUM, Chain.TRON]
    root_chain: Chain = Chain.ETHEREUM
    root_address: str | None = None
    max_hops: int = Field(default=8, ge=1, le=20)
    max_cross_chain_hops: int = Field(default=2, ge=0, le=5)
    max_nodes: int = Field(default=500, ge=1, le=2000)
    max_edges: int = Field(default=2000, ge=1, le=10000)
    max_bridge_interactions: int = Field(default=50, ge=1, le=500)
    max_transactions: int = Field(default=500, ge=1, le=5000)
    max_duration: int = Field(default=60, ge=1, le=300)

class CrossChainSummary(BaseModel):
    chains: list[Chain] = []
    cross_chain_movements: int = 0
    bridge_interactions: int = 0
    new_wallets: int = 0
    unresolved_links: int = 0
    strong_or_exact_links: int = 0
    status: str = "NOT_ANALYZED"

class CrossChainPatternObservation(BaseModel):
    pattern_id: str
    case_id: str
    trace_id: str
    pattern_type: str
    status: PatternStatus = PatternStatus.OBSERVED
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    severity: PatternSeverity = PatternSeverity.INFO
    description: str
    explanation: str
    link_ids: list[str] = []
    evidence_ids: list[str] = []
    metadata: dict = {}
    fingerprint: str
    observed_at: datetime
