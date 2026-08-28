from pydantic import BaseModel
from ..domain import CapabilityStatus


class GraphProjectionStatus(BaseModel):
    provider: str = "neo4j"
    status: CapabilityStatus
    detail: str


class GraphQueryResult(BaseModel):
    case_id: str
    nodes: list[dict] = []
    edges: list[dict] = []
    evidence_ids: list[str] = []
    status: CapabilityStatus = CapabilityStatus.SUPPORTED
    note: str = ""
