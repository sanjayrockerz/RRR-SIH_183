from collections import defaultdict
from datetime import datetime
from .domain import *

_rank={ConfidenceLevel.UNKNOWN:0,ConfidenceLevel.LOW:1,ConfidenceLevel.MEDIUM:2,ConfidenceLevel.HIGH:3,ConfidenceLevel.CONFIRMED:4}

class AttributionEngine:
    def __init__(self,entities:list[Entity],sources:list[AttributionSource],records:list[AddressAttribution]):
        self.entities={e.entity_id:e for e in entities}; self.sources={s.source_id:s for s in sources}; self.records=records
    def resolve(self,chain:Chain,address:str,at_time:datetime|None=None)->ResolvedAttribution:
        records=[r for r in self.records if r.chain==chain and r.address.lower()==address.lower() and (not at_time or (not r.first_seen or r.first_seen<=at_time) and (not r.last_verified or at_time<=r.last_verified))]
        grouped=defaultdict(list)
        for r in records: grouped[r.entity_id].append(r)
        candidates=[]
        for entity_id,rows in grouped.items():
            entity=self.entities.get(entity_id)
            if not entity: continue
            sources=[self.sources[r.source_id] for r in rows if r.source_id in self.sources]
            confidence=max((r.confidence for r in rows),key=lambda x:_rank[x],default=ConfidenceLevel.UNKNOWN)
            candidates.append(AttributionCandidate(entity=entity,attributions=rows,confidence=confidence,supporting_sources=sources,explanation=f"{len(rows)} attribution observation(s) from {len(sources)} source(s); confidence reflects source-backed attribution records, not calibrated probability."))
        candidates.sort(key=lambda c:(-_rank[c.confidence],-len(c.supporting_sources),c.entity.name))
        conflict=len({c.entity.entity_id for c in candidates})>1
        selected=candidates[0].entity.entity_id if len(candidates)==1 else None
        return ResolvedAttribution(chain=chain,address=address.lower(),candidates=candidates,selected_entity_id=selected,conflict=conflict,explanation="Conflict requires investigator review." if conflict else ("One externally sourced candidate was found." if candidates else "No externally sourced attribution was found."))

class NearestEntityResolver:
    def __init__(self,engine:AttributionEngine): self.engine=engine
    def resolve(self,trace:TraceResult)->list[NearestEntityResult]:
        results=[]
        for node in trace.nodes:
            resolved=self.engine.resolve(node.chain,node.address)
            for candidate in resolved.candidates:
                path=next((p for p in trace.paths if node.address in p.node_ids),None)
                if not path: continue
                evidence=[e for edge in path.edges for e in trace.evidence if e.evidence_id==edge.evidence_id]
                results.append(NearestEntityResult(entity=candidate.entity,address=node.address,chain=node.chain,hop_distance=node.depth,path=path,confidence=candidate.confidence,role=candidate.attributions[0].role,supporting_attributions=candidate.attributions,supporting_sources=candidate.supporting_sources,evidence=evidence,explanation="Observed flow reaches an address attributed by external source data; this does not establish ownership or criminal involvement."))
        return sorted(results,key=lambda r:(r.hop_distance,-_rank[r.confidence],-_rank[max((s.reliability_level for s in r.supporting_sources),key=lambda x:_rank[x],default=ConfidenceLevel.UNKNOWN)]))
