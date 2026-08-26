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
