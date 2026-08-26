"""Explainable behavioral observations over a bounded TraceResult.

This module intentionally produces observations, not risk scores or criminality
conclusions. Detectors consume the graph facts already returned by Phase 3 and
optional source-backed Phase 4 attribution results.
"""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from uuid import uuid4

from .domain import (
    ConfidenceLevel, GraphEdge, NearestEntityResult, PatternDetectionConfig,
    PatternObservation, PatternSeverity, PatternStatus, PatternType, TraceResult,
)


def _time(edge: GraphEdge) -> datetime | None:
    return edge.transfer.timestamp


def _amount(edge: GraphEdge) -> Decimal | None:
    try:
        return Decimal(edge.transfer.amount)
    except (InvalidOperation, ValueError):
        return None


def _window(edges: list[GraphEdge]) -> tuple[datetime | None, datetime | None]:
    dates = [d for edge in edges if (d := _time(edge)) is not None]
    return (min(dates), max(dates)) if dates else (None, None)


class PatternDetector:
    pattern_type: PatternType
    def detect(self, trace: TraceResult, config: PatternDetectionConfig, attributions: list[NearestEntityResult]) -> list[PatternObservation]:
        raise NotImplementedError


class PatternEngine:
    def __init__(self, config: PatternDetectionConfig | None = None, detectors: list[PatternDetector] | None = None):
        self.config = config or PatternDetectionConfig()
        self.detectors = detectors or [
            RapidHopDetector(), FanOutDetector(), FanInDetector(), PeelChainDetector(),
            ConsolidationDetector(), BurstActivityDetector(), DormantActivationDetector(),
            MixerInteractionDetector(), BridgeInteractionDetector(), EntityExposureDetector(),
        ]

    def analyze(self, trace: TraceResult, attributions: list[NearestEntityResult] | None = None) -> list[PatternObservation]:
        observations: list[PatternObservation] = []
        for detector in self.detectors:
            observations.extend(detector.detect(trace, self.config, attributions or []))
        unique: dict[str, PatternObservation] = {}
        for observation in observations:
            observation.fingerprint = fingerprint(observation)
            unique[observation.fingerprint] = observation
        return list(unique.values())


def fingerprint(observation: PatternObservation) -> str:
    payload = {
        "case_id": observation.case_id, "trace_id": observation.trace_id,
        "pattern_type": observation.pattern_type, "nodes": sorted(set(observation.affected_nodes)),
        "transactions": sorted(set(observation.transaction_hashes)),
    }
    return sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _observation(trace: TraceResult, pattern_type: PatternType, description: str, explanation: str,
                 edges: list[GraphEdge], nodes: list[str], severity: PatternSeverity = PatternSeverity.MEDIUM,
                 confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM, metadata: dict | None = None,
                 status: PatternStatus = PatternStatus.OBSERVED) -> PatternObservation:
    first, last = _window(edges)
    observed = last or first or datetime.now(timezone.utc)
    return PatternObservation(
        pattern_id=str(uuid4()), case_id=trace.case_id, trace_id=trace.trace_id,
        pattern_type=pattern_type, status=status, confidence_level=confidence, severity=severity,
        description=description, explanation=explanation, observed_at=observed,
        first_observed_at=first, last_observed_at=last, affected_nodes=list(dict.fromkeys(nodes)),
        affected_edges=[edge.edge_id for edge in edges], transaction_hashes=list(dict.fromkeys(edge.transaction_hash for edge in edges)),
        evidence_ids=list(dict.fromkeys(edge.evidence_id for edge in edges if edge.evidence_id)), metadata=metadata or {},
    )


def _paths(trace: TraceResult) -> list[list[GraphEdge]]:
    return [path.edges for path in trace.paths if path.edges] or [[edge] for edge in trace.edges]


class RapidHopDetector(PatternDetector):
    pattern_type = PatternType.RAPID_HOP
    def detect(self, trace, config, attributions):
        results=[]
        for path in _paths(trace):
            ordered=sorted(path, key=lambda e: (_time(e) or datetime.max.replace(tzinfo=timezone.utc), e.edge_id))
            for start in range(0, max(0, len(ordered)-config.rapid_hop_minimum_hops+1)):
                sequence=ordered[start:start+config.rapid_hop_minimum_hops]
                if any(sequence[i].target != sequence[i+1].source for i in range(len(sequence)-1)): continue
                times=[_time(e) for e in sequence]
                if any(t is None for t in times): continue
                gaps=[(times[i+1]-times[i]).total_seconds() for i in range(len(times)-1)]
                if max(gaps, default=0) > config.rapid_hop_max_interhop_seconds: continue
                values=[_amount(e) for e in sequence]
                if config.rapid_hop_minimum_value_retention and values[0] and values[-1] and values[-1] / values[0] < Decimal(str(config.rapid_hop_minimum_value_retention)): continue
                results.append(_observation(trace, self.pattern_type,
                    f"{len(sequence)} consecutive wallet-to-wallet transfers were observed within {int((times[-1]-times[0]).total_seconds())} seconds.",
                    f"A connected path {sequence[0].source} → {sequence[-1].target} contains {len(sequence)} observed transfers and every inter-hop interval is within the configured {config.rapid_hop_max_interhop_seconds}-second threshold.",
                    sequence, [sequence[0].source] + [e.target for e in sequence], PatternSeverity.HIGH, ConfidenceLevel.HIGH,
                    {"minimum_hops":config.rapid_hop_minimum_hops,"max_interhop_seconds":config.rapid_hop_max_interhop_seconds,"elapsed_seconds":(times[-1]-times[0]).total_seconds()}))
        return results


class FanOutDetector(PatternDetector):
    pattern_type = PatternType.FAN_OUT
    def detect(self, trace, config, attributions): return _fan_detector(trace, config, True, self.pattern_type)


class FanInDetector(PatternDetector):
    pattern_type = PatternType.FAN_IN
    def detect(self, trace, config, attributions): return _fan_detector(trace, config, False, self.pattern_type)


def _fan_detector(trace, config, outbound, pattern_type):
    groups=defaultdict(list)
    for edge in trace.edges:
        if _time(edge) is None: continue
        groups[edge.source if outbound else edge.target].append(edge)
    results=[]
    threshold=config.fan_out_minimum_destinations if outbound else config.fan_in_minimum_sources
    for address, edges in groups.items():
        edges=sorted(edges,key=lambda e:_time(e))
        for start in range(len(edges)):
            window=[e for e in edges[start:] if (_time(e)-_time(edges[start])).total_seconds() <= config.fan_time_window_seconds]
            counterpart={e.target if outbound else e.source for e in window}
            if len(counterpart)<threshold: continue
            values=[_amount(e) for e in window if _amount(e) is not None]
            if config.fan_value_threshold and not any(v>=Decimal(str(config.fan_value_threshold)) for v in values): continue
            first,last=_window(window)
            results.append(_observation(trace,pattern_type,
                f"One address was observed transferring to {len(counterpart) if outbound else len(counterpart)} distinct addresses within the configured time window.",
                f"Observed {'outbound distribution from' if outbound else 'inbound consolidation at'} {address} involving {len(counterpart)} distinct counterparties between {first.isoformat()} and {last.isoformat()}.",
                window,[address]+list(counterpart),PatternSeverity.MEDIUM,ConfidenceLevel.MEDIUM,
                {"address":address,"counterparty_count":len(counterpart),"time_window_seconds":config.fan_time_window_seconds,"total_amount":str(sum(values,Decimal('0')))}))
            break
    return results


class PeelChainDetector(PatternDetector):
    pattern_type = PatternType.PEEL_CHAIN
    def detect(self, trace, config, attributions):
        results=[]
        for path in _paths(trace):
            if len(path)<config.peel_chain_minimum_hops: continue
            ratios=[]; valid=True
            for incoming,outgoing in zip(path,path[1:]):
                a,b=_amount(incoming),_amount(outgoing)
                if not a or not b or a<=0 or b>a: valid=False; break
                ratios.append((a-b)/a)
            if not valid or not ratios or not all(config.peel_chain_minimum_retention_ratio <= r <= config.peel_chain_maximum_retention_ratio for r in ratios): continue
            results.append(_observation(trace,self.pattern_type,"A connected flow repeatedly forwarded most of the prior observed amount while retaining a smaller residual.",f"Potential peel-chain-like flow observed across {len(path)} consecutive transfers. The residual ratios were {', '.join(f'{float(r):.2%}' for r in ratios)}; this is an observed value relationship, not a laundering conclusion.",path,[path[0].source]+[e.target for e in path],PatternSeverity.MEDIUM,ConfidenceLevel.MEDIUM,{"retention_ratios":[str(r) for r in ratios]}))
        return results


class ConsolidationDetector(FanInDetector):
    pattern_type = PatternType.CONSOLIDATION
    def detect(self, trace, config, attributions):
        results=super().detect(trace,config,attributions)
        for result in results: result.description="Multiple observed source wallets consolidated funds at a common destination."; result.explanation += " A subsequent movement is not required to establish this observation."
        return results


class BurstActivityDetector(PatternDetector):
    pattern_type = PatternType.BURST_ACTIVITY
    def detect(self, trace, config, attributions):
        edges=sorted([e for e in trace.edges if _time(e)],key=lambda e:_time(e)); results=[]
        for start in range(len(edges)):
            window=[e for e in edges[start:] if (_time(e)-_time(edges[start])).total_seconds()<=config.burst_window_seconds]
            if len(window)>=config.burst_minimum_transactions:
                results.append(_observation(trace,self.pattern_type,f"High transaction density observed: {len(window)} transfers within {config.burst_window_seconds} seconds.",f"The available trace contains {len(window)} observed transfer edges in the window beginning { _time(window[0]).isoformat() }. No statistical anomaly claim is made because no historical baseline was supplied.",window,[n for e in window for n in (e.source,e.target)],PatternSeverity.LOW,ConfidenceLevel.MEDIUM,{"transaction_count":len(window),"window_seconds":config.burst_window_seconds})); break
        return results


class DormantActivationDetector(PatternDetector):
    pattern_type = PatternType.DORMANT_ACTIVATION
    def detect(self, trace, config, attributions):
        by_source=defaultdict(list)
        for edge in trace.edges:
            if _time(edge): by_source[edge.source].append(edge)
        results=[]
        for address, edges in by_source.items():
            edges.sort(key=lambda e:_time(e));
            for previous,current in zip(edges,edges[1:]):
                inactivity=(_time(current)-_time(previous)).total_seconds()
                burst=[e for e in edges if 0 <= (_time(e)-_time(current)).total_seconds() <= config.dormant_activity_window_seconds]
                if inactivity>=config.dormant_inactivity_seconds and len(burst)>=config.dormant_minimum_activity_count:
                    results.append(_observation(trace,self.pattern_type,f"A long inactivity interval was followed by {len(burst)} observed transfers in a short activity window.",f"The available observation window shows no outgoing transfer from {address} between { _time(previous).isoformat() } and { _time(current).isoformat() } for {int(inactivity)} seconds, followed by {len(burst)} transfers within {config.dormant_activity_window_seconds} seconds. This is not a claim of wallet-wide dormancy beyond the available data.",burst,[address]+[e.target for e in burst],PatternSeverity.MEDIUM,ConfidenceLevel.LOW,{"inactivity_seconds":inactivity,"activity_count":len(burst),"observation_window_limited":True})); break
        return results


class MixerInteractionDetector(PatternDetector):
    pattern_type = PatternType.MIXER_INTERACTION
    def detect(self, trace, config, attributions): return _entity_detector(trace, attributions, "MIXER", self.pattern_type, "mixer")


class BridgeInteractionDetector(PatternDetector):
    pattern_type = PatternType.BRIDGE_INTERACTION
    def detect(self, trace, config, attributions):
        results=_entity_detector(trace, attributions, "BRIDGE", self.pattern_type, "bridge")
        for result in results: result.explanation += " Cross-chain continuation is not currently resolved."
        return results


class EntityExposureDetector(PatternDetector):
    pattern_type = PatternType.ENTITY_EXPOSURE
    def detect(self, trace, config, attributions):
        results=[]
        for item in attributions:
            edges=item.path.edges
            results.append(_observation(trace,self.pattern_type,f"Observed graph path reaches an address attributed to {item.entity.name}.",f"The observed path reaches {item.address} at {item.hop_distance} hops. Phase 4 attribution identifies the candidate entity as {item.entity.name} with {item.confidence} confidence from source-backed records; this does not establish ownership.",edges,[n for e in edges for n in (e.source,e.target)],PatternSeverity.INFO,item.confidence,{"entity_id":item.entity.entity_id,"entity_name":item.entity.name,"address":item.address,"hop_distance":item.hop_distance,"role":item.role}))
        return results


def _entity_detector(trace, attributions, entity_type, pattern_type, label):
    results=[]
    for item in attributions:
        if item.entity.entity_type != entity_type: continue
        edges=[edge for edge in trace.edges if edge.source.lower()==item.address.lower() or edge.target.lower()==item.address.lower()]
        if not edges: edges=item.path.edges
        results.append(_observation(trace,pattern_type,f"Observed interaction with an address/contract attributed to a known {label}.",f"An observed graph edge touches {item.address}, which Phase 4 attribution associates with {item.entity.name}. The observation is source-backed and does not establish criminal use.",edges,[item.address],PatternSeverity.MEDIUM,item.confidence,{"entity_id":item.entity.entity_id,"entity_name":item.entity.name,"address":item.address,"hop_distance":item.hop_distance}))
    return results
