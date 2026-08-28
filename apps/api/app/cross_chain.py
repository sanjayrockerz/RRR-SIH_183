"""Chain registry, bridge detection, correlation, and bounded cross-chain graph analysis."""
from collections import defaultdict, deque
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4, uuid5, NAMESPACE_URL
import networkx as nx

from .domain import *
from .config import settings


class ChainRegistry:
    def __init__(self, capabilities: list[ChainCapability] | None = None):
        self._items={item.chain_id:item for item in (capabilities or self.default_capabilities())}

    @staticmethod
    def default_capabilities():
        return [
            ChainCapability(chain_id=Chain.ETHEREUM,name="Ethereum",family="EVM",native_asset="ETH",address_format="0x + 40 hex characters",explorer_base_url="https://etherscan.io",block_time_seconds=12,finality_model="probabilistic",provider="Alchemy Ethereum",historical_capability=CapabilityStatus.SUPPORTED if settings.alchemy_api_key else CapabilityStatus.NOT_CONFIGURED,realtime_capability=CapabilityStatus.NOT_CONFIGURED,token_transfer_capability=CapabilityStatus.SUPPORTED if settings.alchemy_api_key else CapabilityStatus.NOT_CONFIGURED,bridge_detection_capability=CapabilityStatus.SUPPORTED,note="Historical Alchemy adapter; realtime state is reported by the realtime adapter."),
            ChainCapability(chain_id=Chain.TRON,name="Tron",family="TRON",native_asset="TRX",address_format="Base58 T + 33 characters",explorer_base_url="https://tronscan.org/#/transaction/",block_time_seconds=3,finality_model="delegated-finality",provider="TronGrid",historical_capability=CapabilityStatus.NOT_CONFIGURED,realtime_capability=CapabilityStatus.NOT_CONFIGURED,token_transfer_capability=CapabilityStatus.NOT_CONFIGURED,bridge_detection_capability=CapabilityStatus.SUPPORTED,note="Adapter boundary is available; configure TRONGRID_API_KEY for historical access."),
        ]

    @classmethod
    def default(cls): return cls()
    def get(self, chain: Chain):
        try: return self._items[chain]
        except KeyError as exc: raise ValueError(f"Unsupported chain: {chain}") from exc
    def list(self): return list(self._items.values())
    def node_id(self, chain: Chain, address: str): return f"{chain.value}:{normalize_address(chain,address)}"


class BridgeRegistry:
    def __init__(self, definitions: list[BridgeDefinition] | None = None):
        self._definitions={item.bridge_id:item for item in (definitions or [])}
        self._contract_index={}
        for definition in self._definitions.values():
            for chain, contracts in definition.deposit_contracts.items():
                for contract in contracts: self._contract_index[(chain,normalize_address(chain,contract),"BRIDGE_DEPOSIT")]=definition
            for chain, contracts in definition.withdrawal_contracts.items():
                for contract in contracts: self._contract_index[(chain,normalize_address(chain,contract),"BRIDGE_WITHDRAWAL")]=definition
            for chain, contracts in definition.router_contracts.items():
                for contract in contracts: self._contract_index[(chain,normalize_address(chain,contract),"CONTRACT_INTERACTION")]=definition
    def list(self): return list(self._definitions.values())
    def match(self, chain: Chain, address: str, interaction_type: str):
        return self._contract_index.get((chain,normalize_address(chain,address),interaction_type))


class BridgeDetectionEngine:
    def __init__(self, registry: BridgeRegistry): self.registry=registry
    def detect(self, transfers: list[Transfer], evidence_by_tx: dict[str,list[str]] | None=None):
        result=[]; evidence_by_tx=evidence_by_tx or {}
        for transfer in transfers:
            candidates=[]
            raw_observation=(transfer.raw_reference or {}).get("cross_chain_observation",{})
            bridge_address=raw_observation.get("bridge_contract") or transfer.destination
            definition=self.registry.match(transfer.chain,bridge_address,"BRIDGE_DEPOSIT")
            if definition: candidates.append(("BRIDGE_DEPOSIT",definition,bridge_address))
            bridge_address=raw_observation.get("bridge_contract") or transfer.source
            definition=self.registry.match(transfer.chain,bridge_address,"BRIDGE_WITHDRAWAL")
            if definition: candidates.append(("BRIDGE_WITHDRAWAL",definition,bridge_address))
            for interaction_type,bridge,contract in candidates:
                raw=transfer.raw_reference or {}
                result.append(BridgeInteraction(interaction_id=str(uuid4()),bridge_id=bridge.bridge_id,bridge_name=bridge.name,interaction_type=interaction_type,source_chain=transfer.chain,destination_chain=raw.get("destination_chain"),transaction_hash=transfer.tx_hash,bridge_contract=contract,source_address=transfer.source,recipient=raw.get("destination_address") or (transfer.destination if interaction_type=="BRIDGE_DEPOSIT" else transfer.destination),asset=transfer.asset,amount=transfer.amount,timestamp=transfer.timestamp,message_id=raw.get("message_id") or raw.get("messageId"),nonce=str(raw.get("nonce")) if raw.get("nonce") is not None else None,evidence_ids=evidence_by_tx.get(transfer.tx_hash,[]),confidence=ConfidenceLevel.MEDIUM,source=transfer.provider,explanation=f"Observed {interaction_type.lower().replace('_',' ')} involving the source-backed bridge contract {contract}; destination-chain continuation is not established by this observation alone.",raw_reference=raw))
        return result


class CrossChainCorrelationEngine:
    def correlate(self, interactions: list[BridgeInteraction], destination_transfers: list[Transfer], definition: BridgeDefinition | None = None):
        links=[]
        for interaction in interactions:
            # A missing destination chain is an evidence gap, not a wildcard.
            # Do not correlate an observation to an arbitrary network merely
            # because timing or asset symbols happen to be similar.
            candidates=[t for t in destination_transfers if interaction.destination_chain is not None and interaction.destination_chain == t.chain and (not interaction.timestamp or not t.timestamp or abs((t.timestamp-interaction.timestamp).total_seconds()) <= 86400)]
            if not candidates:
                links.append(self._unresolved(interaction)); continue
            best=max(candidates,key=lambda t:self._score(interaction,t))
            score,reasons=self._score(interaction,best,with_reasons=True)
            # Asset/timestamp similarity alone is not a defensible cross-chain
            # link. Require a bridge message, recipient continuity, or equivalent
            # high-signal source evidence before asserting a destination.
            level="EXACT" if score>=0.95 else "STRONG" if score>=0.55 else "UNRESOLVED"
            band=ConfidenceLevel.CONFIRMED if level=="EXACT" else ConfidenceLevel.HIGH if level=="STRONG" else ConfidenceLevel.MEDIUM if level=="PROBABLE" else ConfidenceLevel.LOW if level=="POSSIBLE" else ConfidenceLevel.UNKNOWN
            if level == "UNRESOLVED":
                links.append(self._unresolved(interaction)); continue
            destination=best.destination
            destination_evidence=(best.raw_reference or {}).get("evidence_ids", [])
            correlation_id=sha256(f"{interaction.transaction_hash}|{best.tx_hash}|{interaction.bridge_id}".encode()).hexdigest()
            links.append(CrossChainLink(link_id=str(uuid5(NAMESPACE_URL,f"rrr:cross-chain:{correlation_id}")),source=ChainAddress(chain=interaction.source_chain,address=interaction.source_address),destination=ChainAddress(chain=best.chain,address=destination),source_transaction_hash=interaction.transaction_hash,destination_transaction_hash=best.tx_hash,bridge_id=interaction.bridge_id,correlation_id=correlation_id,correlation_level=level,confidence_score=score,confidence_band=band,evidence_count=len(set(interaction.evidence_ids + destination_evidence)),correlation_reasons=reasons,evidence_ids=list(dict.fromkeys(interaction.evidence_ids + destination_evidence)),provenance_source="CrossChainCorrelationEngine",explanation="Inferred cross-chain relationship; " + ("; ".join(reasons) if reasons else "no qualifying correlation signal"),asset=interaction.asset,amount=interaction.amount,timestamp=interaction.timestamp,bridge_protocol=interaction.bridge_name,created_at=datetime.now(timezone.utc)))
        return links
    def _score(self, interaction, transfer, with_reasons=False):
        score=0.0; reasons=[]; raw=transfer.raw_reference or {}
        if interaction.message_id and raw.get("message_id") == interaction.message_id: score+=0.7; reasons.append("matching bridge message ID")
        if interaction.recipient and normalize_address(transfer.chain,interaction.recipient) in {normalize_address(transfer.chain,transfer.source),normalize_address(transfer.chain,transfer.destination)}: score+=0.25; reasons.append("matching destination address")
        if interaction.asset.lower()==transfer.asset.lower(): score+=0.1; reasons.append("matching asset symbol; contract mapping still requires verification")
        if interaction.timestamp and transfer.timestamp:
            elapsed=abs((transfer.timestamp-interaction.timestamp).total_seconds())
            if elapsed<=300: score+=0.15; reasons.append("temporal correlation within five minutes")
            elif elapsed<=3600: score+=0.05; reasons.append("temporal correlation within one hour")
        if interaction.amount==transfer.amount: score+=0.1; reasons.append("matching observed amount")
        score=min(score,1.0)
        return (score,reasons) if with_reasons else score
    def _unresolved(self, interaction):
        correlation_id=sha256(f"{interaction.transaction_hash}|unresolved|{interaction.bridge_id}".encode()).hexdigest()
        return CrossChainLink(link_id=str(uuid5(NAMESPACE_URL,f"rrr:cross-chain:{correlation_id}")),source=ChainAddress(chain=interaction.source_chain,address=interaction.source_address),destination=None,source_transaction_hash=interaction.transaction_hash,destination_transaction_hash="",bridge_id=interaction.bridge_id,correlation_id=correlation_id,correlation_level="UNRESOLVED",confidence_score=0,confidence_band=ConfidenceLevel.UNKNOWN,evidence_count=len(interaction.evidence_ids),correlation_reasons=[],evidence_ids=interaction.evidence_ids,provenance_source="CrossChainCorrelationEngine",explanation="Bridge interaction observed, but no destination-chain transaction was correlated; no destination address is asserted.",asset=interaction.asset,amount=interaction.amount,timestamp=interaction.timestamp,bridge_protocol=interaction.bridge_name,created_at=datetime.now(timezone.utc))


class CrossChainGraphBuilder:
    def __init__(self, registry: ChainRegistry | None = None): self.registry=registry or ChainRegistry.default()
    def build(self, transfers: list[Transfer], links: list[CrossChainLink], root_chain: Chain, root_address: str, limits: CrossChainAnalyzeRequest | None = None):
        graph=nx.MultiDiGraph(); edges=[]; nodes={}; limits=limits or CrossChainAnalyzeRequest()
        def add_node(chain,address,node_type="WALLET"):
            node_id=self.registry.node_id(chain,address)
            if node_id not in nodes:
                nodes[node_id]=CrossChainNode(node_id=node_id,chain=chain,address=address,node_type=node_type)
                graph.add_node(node_id)
            return node_id
        for transfer in transfers[:limits.max_transactions]:
            source=add_node(transfer.chain,transfer.source); target=add_node(transfer.chain,transfer.destination)
            edge=CrossChainEdge(edge_id=str(uuid4()),edge_type="TOKEN_TRANSFER" if transfer.transfer_type=="token" else "TRANSFER",source_node=source,destination_node=target,chain=transfer.chain,transaction_hash=transfer.tx_hash,asset=transfer.asset,amount=transfer.amount,timestamp=transfer.timestamp,evidence_ids=[],observed_or_inferred="OBSERVED",metadata={"provider":transfer.provider})
            edges.append(edge); graph.add_edge(source,target,key=edge.edge_id,edge=edge)
        for link in links[:limits.max_bridge_interactions]:
            if not link.destination: continue
            source=add_node(link.source.chain,link.source.address); target=add_node(link.destination.chain,link.destination.address)
            bridge_id=f"bridge:{link.bridge_id}"
            if bridge_id not in nodes:
                nodes[bridge_id]=CrossChainNode(node_id=bridge_id,chain=link.source.chain,address=link.bridge_id,node_type="BRIDGE",metadata={"protocol":link.bridge_id})
                graph.add_node(bridge_id)
            deposit=CrossChainEdge(edge_id=str(uuid4()),edge_type="BRIDGE_DEPOSIT",source_node=source,destination_node=bridge_id,chain=link.source.chain,destination_chain=link.destination.chain,transaction_hash=link.source_transaction_hash,asset=link.asset if hasattr(link,"asset") else None,amount=link.amount if hasattr(link,"amount") else None,bridge_id=link.bridge_id,link_id=link.link_id,confidence_band=link.confidence_band,evidence_ids=link.evidence_ids,observed_or_inferred="OBSERVED",metadata={"correlation_level":link.correlation_level,"reasons":link.correlation_reasons})
            bridge=CrossChainEdge(edge_id=str(uuid4()),edge_type="CROSS_CHAIN_LINK",source_node=bridge_id,destination_node=target,chain=link.source.chain,destination_chain=link.destination.chain,transaction_hash=link.source_transaction_hash,destination_transaction_hash=link.destination_transaction_hash or None,bridge_id=link.bridge_id,link_id=link.link_id,confidence_band=link.confidence_band,evidence_ids=link.evidence_ids,observed_or_inferred="INFERRED",metadata={"correlation_level":link.correlation_level,"reasons":link.correlation_reasons})
            edges.extend([deposit,bridge]); graph.add_edge(source,bridge_id,key=deposit.edge_id,edge=deposit); graph.add_edge(bridge_id,target,key=bridge.edge_id,edge=bridge)
        root=self.registry.node_id(root_chain,root_address); reachable={root}; queue=deque([(root,0,0)])
        while queue:
            current,hops,cross=queue.popleft()
            if hops>=limits.max_hops: continue
            for _,target,key,data in graph.out_edges(current,keys=True,data=True):
                edge=data["edge"]; next_cross=cross+(1 if edge.edge_type=="CROSS_CHAIN_LINK" else 0)
                if next_cross>limits.max_cross_chain_hops or target in reachable: continue
                reachable.add(target); queue.append((target,hops+1,next_cross))
        selected_edges=[e for e in edges if e.source_node in reachable and e.destination_node in reachable][:limits.max_edges]
        selected_nodes=[nodes[n] for n in reachable if n in nodes][:limits.max_nodes]
        chains=list(dict.fromkeys(n.chain for n in selected_nodes)); cross_links=[link for link in links if self.registry.node_id(link.source.chain,link.source.address) in reachable]
        edge_by_pair=defaultdict(list)
        for edge in selected_edges: edge_by_pair[(edge.source_node,edge.destination_node)].append(edge)
        paths=[]
        for target in reachable:
            if target==root: continue
            try: node_path=nx.shortest_path(graph,root,target)
            except nx.NetworkXNoPath: continue
            path_edges=[]
            for source,target_node in zip(node_path,node_path[1:]):
                candidates=edge_by_pair.get((source,target_node),[])
                if candidates: path_edges.append(candidates[0].edge_id)
            paths.append(CrossChainPath(path_id=str(uuid4()),node_ids=node_path,edge_ids=path_edges,chains=list(dict.fromkeys(nodes[n].chain for n in node_path if n in nodes)),confidence=ConfidenceLevel.HIGH if any(e in {x.edge_id for x in selected_edges if x.edge_type=="CROSS_CHAIN_LINK"} for e in path_edges) else ConfidenceLevel.CONFIRMED))
        partial=len(selected_edges)<len(edges) or len(selected_nodes)<len(nodes) or any(link.correlation_level=="UNRESOLVED" for link in cross_links)
        return CrossChainTrace(trace_id=str(uuid4()),case_id="",root=ChainAddress(chain=root_chain,address=root_address),chains_visited=chains,cross_chain_hops=sum(1 for edge in selected_edges if edge.edge_type=="CROSS_CHAIN_LINK"),cross_chain_links=cross_links,nodes=selected_nodes,edges=selected_edges,paths=paths,status="PARTIAL" if partial else "COMPLETED",limitations=["Cross-chain links are inferred and confidence-scored; they are not observed transfers." ] if partial else [],max_hops=limits.max_hops,max_cross_chain_hops=limits.max_cross_chain_hops,max_nodes=limits.max_nodes,max_edges=limits.max_edges,max_bridge_interactions=limits.max_bridge_interactions,max_transactions=limits.max_transactions)
