from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4
import networkx as nx
from .domain import *

class GraphBuilder:
    def build(self, transfers: list[Transfer], root: str, depths: dict[str, int] | None = None):
        graph=nx.MultiDiGraph(); depths=depths or {}
        for transfer in transfers:
            source=transfer.source.lower(); target=transfer.destination.lower()
            if not source or not target: continue
            for address in (source,target):
                graph.add_node(address, address=address, chain=transfer.chain, node_type="CONTRACT" if address == transfer.contract_address else "WALLET")
            edge_id=str(uuid4()); graph.add_edge(source,target,key=edge_id,edge_id=edge_id,transfer=transfer)
        nodes=[]
        for address,data in graph.nodes(data=True):
            incident=list(graph.in_edges(address,keys=True,data=True))+list(graph.out_edges(address,keys=True,data=True))
            dates=[e["transfer"].timestamp for _,_,_,e in incident if e["transfer"].timestamp]
            nodes.append(GraphNode(id=address,address=address,chain=data.get("chain",Chain.ETHEREUM),node_type=data.get("node_type","WALLET"),depth=depths.get(address,0),first_seen=min(dates) if dates else None,last_seen=max(dates) if dates else None,transaction_count=len({e["transfer"].tx_hash for _,_,_,e in incident})))
        edges=[GraphEdge(edge_id=data["edge_id"],source=source,target=target,transfer=data["transfer"],hop=depths.get(source,0),asset_type=data["transfer"].transfer_type,transaction_hash=data["transfer"].tx_hash) for source,target,_,data in graph.edges(keys=True,data=True)]
        return graph,nodes,edges

class GraphAnalyzer:
    def metrics(self, graph, nodes, edges, root, paths=()):
        inbound=sum(1 for edge in edges if edge.target==root); outbound=sum(1 for edge in edges if edge.source==root)
        return TraceMetrics(node_count=len(nodes),edge_count=len(edges),unique_wallet_count=len([n for n in nodes if n.node_type=="WALLET"]),contract_count=len([n for n in nodes if n.node_type=="CONTRACT"]),inbound_edge_count=inbound,outbound_edge_count=outbound,maximum_hop=max((e.hop for e in edges),default=0),path_count=len(paths),unique_transaction_count=len({e.transaction_hash for e in edges}),unique_asset_count=len({e.transfer.asset for e in edges}))
    def paths(self, graph, root, max_paths=100):
        result=[]
        for target in graph.nodes:
            if target==root: continue
            try: path=nx.shortest_path(graph,root,target)
            except nx.NetworkXNoPath: continue
            path_edges=[]
            for source,target_node in zip(path,path[1:]):
                key=next(iter(graph[source][target_node])); data=graph[source][target_node][key]
                path_edges.append(GraphEdge(edge_id=data["edge_id"],source=source,target=target_node,transfer=data["transfer"],hop=len(path_edges)+1,asset_type=data["transfer"].transfer_type,transaction_hash=data["transfer"].tx_hash))
            result.append(TransactionPath(path_id=str(uuid4()),node_ids=path,edges=path_edges))
            if len(result)>=max_paths: break
        return result
    def flows(self, edges):
        grouped=defaultdict(list)
        for edge in edges: grouped[edge.transfer.asset].append(edge)
        flows=[]
        for asset,asset_edges in grouped.items():
            ordered=sorted(asset_edges,key=lambda e:e.transfer.timestamp or datetime.min.replace(tzinfo=timezone.utc))
            times=[e.transfer.timestamp for e in ordered if e.transfer.timestamp]
            elapsed=(max(times)-min(times)).total_seconds() if len(times)>1 else None
            flows.append(FundFlow(flow_id=str(uuid4()),asset=asset,edges=ordered,initial_amount=ordered[0].transfer.amount,final_amount=ordered[-1].transfer.amount,hop_count=len(ordered),elapsed_seconds=elapsed))
        return flows
    def shortest_path(self, graph, source, destination):
        path=nx.shortest_path(graph,source.lower(),destination.lower())
        return path

def amount_for_filter(transfer: Transfer) -> Decimal:
    try: return Decimal(transfer.amount)
    except InvalidOperation: return Decimal("0")
