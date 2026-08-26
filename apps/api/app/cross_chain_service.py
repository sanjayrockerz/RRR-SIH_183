"""Application service for bounded, evidence-backed cross-chain analysis."""
from .cross_chain import ChainRegistry, BridgeRegistry, BridgeDetectionEngine, CrossChainCorrelationEngine, CrossChainGraphBuilder
from .domain import *
from .config import settings
from pathlib import Path
import json
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

def load_bridge_definitions(path: str):
    file=Path(path)
    if not file.exists(): return []
    try:
        items=json.loads(file.read_text(encoding="utf-8"))
        definitions=[]
        for item in items if isinstance(items,list) else []:
            definitions.append(BridgeDefinition.model_validate(item))
        return definitions
    except (OSError,ValueError,TypeError):
        return []


class CrossChainService:
    def __init__(self, repository, bridge_definitions: list[BridgeDefinition] | None = None, chain_registry: ChainRegistry | None = None):
        self.repository=repository
        self.chain_registry=chain_registry or ChainRegistry.default()
        self.bridge_registry=BridgeRegistry(bridge_definitions if bridge_definitions is not None else load_bridge_definitions(settings.bridge_registry_file))
        self.bridge_detector=BridgeDetectionEngine(self.bridge_registry)
        self.correlation=CrossChainCorrelationEngine()
        self.graph_builder=CrossChainGraphBuilder(self.chain_registry)

    def capabilities(self): return self.chain_registry.list()
    def bridge_definitions(self): return self.bridge_registry.list()

    async def ingest_observation(self, case_id: str, observation: CrossChainObservationCreate):
        WalletCreate(address=observation.transfer.source,chain=observation.transfer.chain)
        WalletCreate(address=observation.transfer.destination,chain=observation.transfer.chain)
        if observation.mode != DataMode.SIMULATED and observation.transfer.provider in {"", "fixture", "SIMULATED EVENT SOURCE"}:
            raise ValueError("Non-simulated cross-chain observations require a configured provider source")
        transfer=observation.transfer.model_copy(update={"raw_reference":{**(observation.transfer.raw_reference or {}),"cross_chain_observation":observation.model_dump(mode="json")}})
        return await self.repository.persist_cross_chain_observation(case_id,observation.model_copy(update={"transfer":transfer}))

    async def analyze(self, case_id: str, request: CrossChainAnalyzeRequest):
        case=await self.repository.get(case_id)
        if not case: raise ValueError("Case not found")
        transfers=[t for t in await self.repository.cross_chain_transfers(case_id) if t.chain in request.chains][:request.max_transactions]
        evidence_by_tx={}
        interactions=self.bridge_detector.detect(transfers,evidence_by_tx)
        for interaction in interactions:
            raw=interaction.raw_reference.get("cross_chain_observation",{}) if interaction.raw_reference else {}
            interaction=interaction.model_copy(update={"destination_chain":raw.get("destination_chain"),"recipient":raw.get("destination_address") or interaction.recipient,"message_id":raw.get("message_id") or interaction.message_id,"nonce":raw.get("nonce") or interaction.nonce})
            await self.repository.persist_bridge_definition(next((d for d in self.bridge_registry.list() if d.bridge_id==interaction.bridge_id)))
            await self.repository.persist_bridge_interaction(case_id,interaction)
        destination_transfers=[t for t in transfers if t.chain != request.root_chain]
        links=self.correlation.correlate(interactions,destination_transfers)
        for link in links: await self.repository.persist_cross_chain_link(case_id,link)
        root_address=request.root_address or (case.wallets[0].address if case.wallets else None)
        if not root_address: raise ValueError("A root address is required for cross-chain analysis")
        trace=self.graph_builder.build(transfers,links,request.root_chain,root_address,request).model_copy(update={"case_id":case_id})
        trace.provider_states=[ProviderCapability(name=f"{item.chain_id.value}:historical",status=item.historical_capability,mode=DataMode.HISTORICAL,note=item.note or "") for item in self.chain_registry.list()]
        await self.repository.persist_cross_chain_trace(trace)
        patterns=[]
        if links:
            evidence=list(dict.fromkeys(e for link in links for e in link.evidence_ids))
            for pattern_type,description in [("CROSS_CHAIN_HOP","Observed movement relationship crosses supported blockchain networks."),("BRIDGE_HOP","Observed bridge interaction has a destination-chain correlation result.")]:
                fingerprint=sha256(json.dumps({"case_id":case_id,"trace_id":trace.trace_id,"pattern_type":pattern_type,"links":sorted(link.link_id for link in links)},sort_keys=True).encode()).hexdigest()
                patterns.append(CrossChainPatternObservation(pattern_id=str(uuid4()),case_id=case_id,trace_id=trace.trace_id,pattern_type=pattern_type,description=description,explanation="This is an evidence-backed behavioral observation. Cross-chain correlation is not a determination of criminality or laundering.",link_ids=[link.link_id for link in links],evidence_ids=evidence,metadata={"correlation_levels":list(dict.fromkeys(link.correlation_level for link in links))},fingerprint=fingerprint,observed_at=datetime.now(timezone.utc)))
            await self.repository.persist_cross_chain_patterns(patterns)
        return trace

    async def links(self,case_id): return await self.repository.cross_chain_links(case_id)
    async def patterns(self,case_id): return await self.repository.cross_chain_patterns(case_id)
    async def summary(self,case_id):
        links=await self.repository.cross_chain_links(case_id)
        chains=list(dict.fromkeys([x.source.chain for x in links]+[x.destination.chain for x in links if x.destination]))
        return CrossChainSummary(chains=chains,cross_chain_movements=len(links),bridge_interactions=len(links),unresolved_links=sum(1 for x in links if x.correlation_level=="UNRESOLVED"),strong_or_exact_links=sum(1 for x in links if x.correlation_level in {"STRONG","EXACT"}),status="ANALYZED" if links else "NOT_ANALYZED")
