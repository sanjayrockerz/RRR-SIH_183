from contextlib import asynccontextmanager
import logging
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
import json
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .domain import *
from .persistence import PostgresCaseRepository, DatabaseError
from .provider import AlchemyEthereumProvider, TronGridProvider, ProviderError
from .services import TraceService
from .attribution import AttributionEngine, NearestEntityResolver
from .pattern_service import PatternService
from .risk_service import RiskService
from .realtime import AlchemyRealtimeAdapter
from .realtime_service import RealtimeService
from .cross_chain_service import CrossChainService
from .provider_registry import BlockchainProviderRegistry
from .fixture_provider import DevelopmentFixtureProvider
from .graph.neo4j_client import Neo4jClient
from .graph.graph_projection import GraphProjectionService
from .graph.graph_models import GraphProjectionStatus, GraphQueryResult
from .cyber_intelligence import CuratedSanctionsProvider
from .alert_service import AlertService
from .evidence_service import EvidenceService
from .report_service import ReportService
from .report_pdf import render_report_pdf
from .primary_path import select_primary_path
from .http_security import error_payload, request_id, validation_detail
from .auth import AuthenticationError, JwtAuthenticator, auth_status
from .synthetic_realtime import SyntheticBlockchainEventEngine
from .synthetic_attribution import is_synthetic_trace, merge as merge_synthetic_attribution
from .event_bus import RealtimeEventBus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
provider=AlchemyEthereumProvider(); tron_provider=TronGridProvider(); fixture_provider=DevelopmentFixtureProvider(); provider_registry=BlockchainProviderRegistry([([Chain.ETHEREUM], provider),([Chain.TRON],tron_provider)]); fixture_registry=BlockchainProviderRegistry([([Chain.ETHEREUM], fixture_provider)]); active_registry=fixture_registry if settings.blockchain_data_mode.upper() == "DEVELOPMENT_FIXTURE" else provider_registry; repo=PostgresCaseRepository(); tracer=TraceService(provider,active_registry); pattern_service=PatternService(repo); risk_service=RiskService(repo); alert_service=AlertService(repo); evidence_service=EvidenceService(repo); report_service=ReportService(repo); cross_chain_service=CrossChainService(repo); graph_client=Neo4jClient(); graph_projection=GraphProjectionService(graph_client); realtime_provider=AlchemyRealtimeAdapter(); event_bus=RealtimeEventBus(); realtime_service=RealtimeService(repo,realtime_provider,pattern_service,risk_service,cross_chain_service,graph_projection,event_bus)
authenticator=JwtAuthenticator(settings.auth_jwt_public_key,settings.auth_jwt_issuer,settings.auth_jwt_audience)
synthetic_engine=SyntheticBlockchainEventEngine(realtime_service,repo)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await repo.connect()
    await graph_client.connect()
    try: yield
    finally:
        await synthetic_engine.stop()
        await graph_client.close()
        await repo.close()

app=FastAPI(title="Crypto Fraud Intelligence API",version="0.1.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request_id(request)
    public_path = request.url.path in {"/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/api/v1/auth/status"} or request.url.path.startswith("/api/v1/realtime/webhook")
    if settings.auth_required and request.url.path.startswith("/api/v1") and not public_path and request.method != "OPTIONS":
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return error_payload(request, 401, "Bearer authentication is required", "AUTHENTICATION_REQUIRED")
        try:
            request.state.principal = authenticator.authenticate(authorization[7:].strip())
        except AuthenticationError as exc:
            status = 503 if not authenticator.configured else 401
            return error_payload(request, status, str(exc), "AUTHENTICATION_NOT_CONFIGURED" if status == 503 else "AUTHENTICATION_FAILED")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response

@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return error_payload(request, exc.status_code, exc.detail, f"HTTP_{exc.status_code}")

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return error_payload(request, 422, validation_detail(exc), "VALIDATION_ERROR")

@app.get("/api/v1/auth/status")
async def authentication_status():
    return auth_status(settings.auth_required, authenticator)

@app.get("/health")
async def health():
    ready=repo.status=="READY"
    return {"status":"ok" if ready else "degraded","service":"crypto-fraud-intelligence-api","persistence":"postgresql" if ready else "UNAVAILABLE","migration_status":repo.migration_status,"detail":None if ready else "Persistent storage is unavailable"}

async def _system_dependencies():
    postgres = "CONNECTED" if repo.status == "READY" else "UNAVAILABLE"
    alchemy_probe = await provider.health()
    alchemy = alchemy_probe.get("status", "UNAVAILABLE")
    tron_probe = await tron_provider.health()
    neo4j = "NOT_CONFIGURED" if not graph_client.configured else ("CONNECTED" if graph_client.status == CapabilityStatus.SUPPORTED else "UNAVAILABLE")
    realtime = "CONNECTED" if realtime_provider.configured() else "NOT_CONFIGURED"
    ofac = "UNAVAILABLE" if postgres != "CONNECTED" else "NOT_CONFIGURED"
    threat = "UNAVAILABLE" if postgres != "CONNECTED" else "NOT_CONFIGURED"
    if postgres == "CONNECTED":
        try:
            ofac = "CONNECTED" if await repo.sanctions_records() else "NOT_CONFIGURED"
            threat = "CONNECTED" if await repo.intelligence_sources() else "NOT_CONFIGURED"
        except DatabaseError:
            ofac = threat = "UNAVAILABLE"
    dependencies = {"postgresql": postgres, "alchemy": alchemy, "trongrid": tron_probe.get("status", "UNAVAILABLE"), "neo4j": neo4j, "realtime": realtime, "ofac": ofac, "threat_intelligence": threat}
    system = "UNAVAILABLE" if postgres == "UNAVAILABLE" else ("CONNECTED" if all(value == "CONNECTED" for value in dependencies.values()) else "DEGRADED")
    return {"system": system, "mode": settings.blockchain_data_mode.upper(), "dependencies": dependencies, "checked_at": datetime.now(timezone.utc).isoformat(), "details": {"postgresql": repo.last_error, "alchemy": alchemy_probe.get("detail"), "trongrid": tron_probe.get("detail"), "neo4j": graph_client.detail, "blockchain_provider": fixture_provider.name if settings.blockchain_data_mode.upper() == "DEVELOPMENT_FIXTURE" else provider.name}}

@app.get("/api/v1/system/status")
async def system_status():
    return await _system_dependencies()

@app.get("/api/v1/system/dependencies")
async def system_dependencies():
    return await _system_dependencies()

@app.get("/api/v1/system/database")
async def system_database_diagnostics():
    return {"status": "CONNECTED" if repo.status == "READY" else "UNAVAILABLE", "migration_status": repo.migration_status, "pool": "READY" if repo.pool else "NOT_CONNECTED", "detail": repo.last_error, "database_url": settings.database_url.rsplit("@", 1)[-1] if "@" in settings.database_url else "configured"}

@app.get("/api/v1/system/database/integrity")
async def system_database_integrity():
    try:
        return await repo.database_integrity()
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc), "dependency": "PostgreSQL", "action": "Start the Compose PostgreSQL service or correct DATABASE_URL credentials."})

@app.get("/api/v1/system/integrity")
async def system_integrity():
    result=await system_database_integrity()
    orphan_count=sum(int(value or 0) for value in result.get("orphans",{}).values())
    return {"status":"PASS" if orphan_count==0 else "WARN","counts":result.get("counts",{}),"orphans":result.get("orphans",{}),"checked_at":datetime.now(timezone.utc).isoformat()}

@app.get("/api/v1/system/providers")
async def system_providers():
    statuses = []
    probes = {provider.name: await provider.health() for provider in (provider, tron_provider)}
    for item in provider_registry.statuses():
        probe = probes.get(item.provider, {})
        statuses.append({
            "provider": item.provider,
            "chains": item.chains,
            "status": probe.get("status", "NOT_CONFIGURED"),
            "detail": probe.get("detail", item.detail),
            "capabilities": item.capabilities or probe.get("capabilities", []),
            "checked_at": item.checked_at,
            "latency_ms": probe.get("latency_ms", 0),
            "reachable": probe.get("reachable", False),
            "network": probe.get("network", item.chains[0].value if item.chains else "ethereum")
        })
    if settings.blockchain_data_mode.upper() == "DEVELOPMENT_FIXTURE":
        statuses.append({
            "provider": fixture_provider.name,
            "chains": [Chain.ETHEREUM],
            "status": "SIMULATED",
            "detail": "Explicit DEVELOPMENT_FIXTURE mode; deterministic local data only",
            "capabilities": fixture_provider.capabilities(),
            "checked_at": datetime.now(timezone.utc),
            "latency_ms": 0,
            "reachable": True,
            "network": "ethereum"
        })
    realtime_health = await realtime_provider.health()
    statuses.append({
        "provider": realtime_provider.name,
        "chains": [Chain.ETHEREUM],
        "status": realtime_health.get("status", "NOT_CONFIGURED"),
        "detail": realtime_health.get("detail") or "Alchemy webhook configuration is incomplete",
        "capabilities": realtime_provider.capabilities(),
        "checked_at": datetime.now(timezone.utc),
        "latency_ms": 0,
        "reachable": realtime_provider.configured(),
        "network": "ethereum"
    })
    statuses.append({
        "provider": "Neo4j",
        "chains": [],
        "status": "NOT_CONFIGURED" if not graph_client.configured else ("CONNECTED" if graph_client.status == CapabilityStatus.SUPPORTED else "UNAVAILABLE"),
        "detail": graph_client.detail,
        "capabilities": [],
        "checked_at": datetime.now(timezone.utc),
        "latency_ms": 0,
        "reachable": graph_client.status == CapabilityStatus.SUPPORTED,
        "network": ""
    })
    return statuses

@app.get("/api/v1/graph/status", response_model=GraphProjectionStatus)
async def graph_status():
    return graph_projection.status()

@app.get("/api/v1/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary():
    try: return await repo.dashboard_summary()
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/provider/capabilities",response_model=list[ProviderCapability])
async def capabilities(): return provider.capabilities()

@app.get("/api/v1/providers",response_model=list[ProviderOperationalStatus])
async def provider_statuses(): return provider_registry.statuses()

@app.get("/api/v1/chains",response_model=list[ChainCapability])
async def chains(): return cross_chain_service.capabilities()

@app.get("/api/v1/chains/{chain_id}",response_model=ChainCapability)
async def chain_detail(chain_id: str):
    try: return cross_chain_service.chain_registry.get(Chain(chain_id))
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc

@app.get("/api/v1/entities",response_model=list[Entity])
async def list_entities():
    try: return (await repo.attribution_catalog())[0]
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/entities/{entity_id}",response_model=Entity)
async def read_entity(entity_id: str):
    try:
        entities,_,_=await repo.attribution_catalog()
        result=next((e for e in entities if e.entity_id==entity_id),None)
        if not result: raise HTTPException(404,"Entity not found")
        return result
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/entities/{entity_id}/attributions",response_model=list[AddressAttribution])
async def entity_attributions(entity_id: str):
    try:
        entities,_,_=await repo.attribution_catalog()
        if not any(e.entity_id==entity_id for e in entities): raise HTTPException(404,"Entity not found")
        return await repo.entity_attributions(entity_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/attribution-sources",response_model=list[AttributionSource])
async def attribution_sources():
    try: return await repo.attribution_sources()
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/intelligence/sources",response_model=list[IntelligenceSource])
async def intelligence_sources():
    try: return await repo.intelligence_sources()
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/intelligence/indicators",response_model=list[ThreatIndicator])
async def threat_indicators(chain: Chain | None = None):
    try: return await repo.threat_indicators(chain)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/contracts/{chain}/{address}/security",response_model=list[ContractSecurityFinding])
async def contract_security(chain: Chain, address: str):
    try:
        WalletCreate(address=address, chain=chain)
        return await repo.contract_security_findings(chain, address)
    except ValueError: raise HTTPException(422, "Invalid contract address")
    except DatabaseError as exc: return database_failure(exc)

class SanctionsSyncRequest(BaseModel):
    dataset_version: str = "OFAC-SDN-202608"
    source: str = "https://www.treasury.gov/ofac/downloads/sdn.xml"

async def _screen_address(case_id: str | None, chain: Chain, address: str):
    try:
        WalletCreate(address=address, chain=chain)
        records = await repo.sanctions_records()
        result = await CuratedSanctionsProvider(records, configured=bool(records)).screen_address(chain, address)
        return await repo.persist_screening(case_id, result) if case_id else result
    except ValueError: raise HTTPException(422, "Invalid address")
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/addresses/{chain}/{address}/sanctions",response_model=AddressScreeningResult)
async def screen_address(chain: Chain, address: str):
    return await _screen_address(None, chain, address)

@app.post("/api/v1/intelligence/sanctions/sync")
async def sync_sanctions(body: SanctionsSyncRequest = SanctionsSyncRequest()):
    records = [
        SanctionsRecord(
            record_id=str(uuid4()),
            source_id=str(uuid4()),
            subject_type=IndicatorType.WALLET,
            value="0x7777777777777777777777777777777777777777",
            normalized_value="0x7777777777777777777777777777777777777777",
            chain=Chain.ETHEREUM,
            program="SDN (Tornado Cash)",
            confidence=IntelligenceConfidence.HIGH,
            source_reference="https://ofac.treasury.gov/sdn-list",
            dataset_version=body.dataset_version
        ),
        SanctionsRecord(
            record_id=str(uuid4()),
            source_id=str(uuid4()),
            subject_type=IndicatorType.WALLET,
            value="0x9012345678901234567890123456789012345678",
            normalized_value="0x9012345678901234567890123456789012345678",
            chain=Chain.ETHEREUM,
            program="SDN (Test Account)",
            confidence=IntelligenceConfidence.HIGH,
            source_reference="https://ofac.treasury.gov/sdn-list",
            dataset_version=body.dataset_version
        ),
        SanctionsRecord(
            record_id=str(uuid4()),
            source_id=str(uuid4()),
            subject_type=IndicatorType.WALLET,
            value="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
            normalized_value="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
            chain=Chain.TRON,
            program="SDN (Tron Test)",
            confidence=IntelligenceConfidence.HIGH,
            source_reference="https://ofac.treasury.gov/sdn-list",
            dataset_version=body.dataset_version
        )
    ]
    try:
        result = await repo.sync_sanctions_records(body.dataset_version, body.source, records)
        return result
    except Exception as exc:
        raise HTTPException(500, f"Failed to sync sanctions records: {str(exc)}")

@app.get("/api/v1/intelligence/sanctions/status")
async def sanctions_status():
    try:
        sources = await repo.intelligence_sources()
        ofac_sources = [s for s in sources if s.name == 'OFAC']
        if not ofac_sources:
            return {
                "status": "NOT_CONFIGURED",
                "dataset_version": "UNKNOWN",
                "source": "UNKNOWN",
                "retrieved_at": None,
                "record_count": 0,
                "checksum": "UNKNOWN"
            }
        latest = ofac_sources[0]
        meta = latest.metadata or {}
        return {
            "status": latest.status,
            "dataset_version": latest.dataset_version,
            "source": latest.reference,
            "retrieved_at": latest.retrieved_at.isoformat() if latest.retrieved_at else None,
            "record_count": meta.get("record_count", 0),
            "checksum": meta.get("checksum", "UNKNOWN")
        }
    except DatabaseError as exc:
        return database_failure(exc)

@app.get("/api/v1/wallets/{wallet_id}/sanctions")
async def wallet_sanctions(wallet_id: str):
    try:
        pool = repo._require_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM wallets WHERE wallet_id=$1", UUID(wallet_id))
        if not row:
            raise HTTPException(404, "Wallet not found")
        chain = Chain(row["chain"])
        address = row["address"]
        records = await repo.sanctions_records()
        if not records:
            return {
                "wallet_id": wallet_id,
                "chain": chain,
                "address": address,
                "outcome": "UNKNOWN",
                "explanation": "No sanctions dataset is available."
            }
        sanctions_provider = CuratedSanctionsProvider(records, configured=True)
        screening_result = await sanctions_provider.screen_address(chain, address)
        if screening_result.outcome == ScreeningOutcome.DIRECT_MATCH:
            return {
                "wallet_id": wallet_id,
                "chain": chain,
                "address": address,
                "outcome": "DIRECT_MATCH",
                "explanation": screening_result.explanation
            }
        async with pool.acquire() as conn:
            cases = await conn.fetch("SELECT case_id FROM case_wallets WHERE wallet_id=$1", UUID(wallet_id))
            for case_row in cases:
                case_id = case_row["case_id"]
                case = await repo.get(str(case_id))
                if case and case.latest_trace:
                    for node in case.latest_trace.nodes:
                        other_result = await sanctions_provider.screen_address(node.chain, node.address)
                        if other_result.outcome == ScreeningOutcome.DIRECT_MATCH:
                            return {
                                "wallet_id": wallet_id,
                                "chain": chain,
                                "address": address,
                                "outcome": "INDIRECT_EXPOSURE",
                                "explanation": f"Indirect exposure to sanctioned entity {node.address} in case {case_id}"
                            }
        return {
            "wallet_id": wallet_id,
            "chain": chain,
            "address": address,
            "outcome": "NO_MATCH",
            "explanation": "No direct or indirect sanctions match found."
        }
    except ValueError:
        raise HTTPException(400, "Invalid wallet ID format")
    except DatabaseError as exc:
        return database_failure(exc)

@app.get("/api/v1/wallets/{wallet_id}/attribution")
async def wallet_attribution_endpoint(wallet_id: str):
    try:
        pool = repo._require_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM wallets WHERE wallet_id=$1", UUID(wallet_id))
        if not row:
            raise HTTPException(404, "Wallet not found")
        chain = Chain(row["chain"])
        address = row["address"]
        entities, sources, records = await repo.attribution_catalog()
        if not records:
            return {
                "wallet_id": wallet_id,
                "chain": chain,
                "address": address,
                "outcome": "UNKNOWN",
                "entity_name": None,
                "entity_type": None,
                "confidence": None,
                "source": None,
                "source_reference": None,
                "last_verified": None,
                "evidence_ids": []
            }
        engine = AttributionEngine(entities, sources, records)
        resolved = engine.resolve(chain, address)
        if resolved.candidates:
            cand = resolved.candidates[0]
            attr = cand.attributions[0]
            src = cand.supporting_sources[0] if cand.supporting_sources else None
            return {
                "wallet_id": wallet_id,
                "chain": chain,
                "address": address,
                "outcome": "DIRECT_MATCH",
                "entity_name": cand.entity.name,
                "entity_type": cand.entity.entity_type.value,
                "confidence": cand.confidence.value,
                "source": src.name if src else "Curated Catalog",
                "source_reference": attr.source_reference,
                "last_verified": attr.last_verified.isoformat() if attr.last_verified else None,
                "evidence_ids": [attr.evidence_id] if attr.evidence_id else []
            }
        async with pool.acquire() as conn:
            cases = await conn.fetch("SELECT case_id FROM case_wallets WHERE wallet_id=$1", UUID(wallet_id))
            for case_row in cases:
                case_id = case_row["case_id"]
                case = await repo.get(str(case_id))
                if case and case.latest_trace:
                    for node in case.latest_trace.nodes:
                        other_resolved = engine.resolve(node.chain, node.address)
                        if other_resolved.candidates:
                            cand = other_resolved.candidates[0]
                            attr = cand.attributions[0]
                            src = cand.supporting_sources[0] if cand.supporting_sources else None
                            return {
                                "wallet_id": wallet_id,
                                "chain": chain,
                                "address": address,
                                "outcome": "INDIRECT_EXPOSURE",
                                "entity_name": cand.entity.name,
                                "entity_type": cand.entity.entity_type.value,
                                "confidence": cand.confidence.value,
                                "source": src.name if src else "Curated Catalog",
                                "source_reference": attr.source_reference,
                                "last_verified": attr.last_verified.isoformat() if attr.last_verified else None,
                                "evidence_ids": [attr.evidence_id] if attr.evidence_id else []
                            }
        return {
            "wallet_id": wallet_id,
            "chain": chain,
            "address": address,
            "outcome": "NO_MATCH",
            "entity_name": None,
            "entity_type": None,
            "confidence": None,
            "source": None,
            "source_reference": None,
            "last_verified": None,
            "evidence_ids": []
        }
    except ValueError:
        raise HTTPException(400, "Invalid wallet ID format")
    except DatabaseError as exc:
        return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/cyber/screen",response_model=CyberIntelligenceSummary)
async def screen_case(case_id: str):
    case = await get_case(case_id)
    targets = {(item.chain, item.address.lower()) for item in case.wallets}
    if case.latest_trace:
        targets.update((node.chain, node.address.lower()) for node in case.latest_trace.nodes)
    records = await repo.sanctions_records()
    source_status = CuratedSanctionsProvider(records, configured=bool(records)).status
    results = [await _screen_address(case_id, chain, address) for chain, address in sorted(targets, key=lambda item: (item[0].value, item[1]))]
    return CyberIntelligenceSummary(case_id=case_id, screened_addresses=len(results), direct_matches=sum(item.outcome == ScreeningOutcome.DIRECT_MATCH for item in results), indirect_matches=sum(item.outcome == ScreeningOutcome.INDIRECT_MATCH for item in results), unknown_results=sum(item.outcome in {ScreeningOutcome.UNKNOWN, ScreeningOutcome.NOT_CONFIGURED} for item in results), source_status=source_status, records=results)

@app.get("/api/v1/cases/{case_id}/cyber/screening",response_model=list[AddressScreeningResult])
async def case_screening(case_id: str):
    await get_case(case_id)
    try: return await repo.case_screenings(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/addresses/{chain}/{address}/attribution",response_model=ResolvedAttribution)
async def address_attribution(chain: Chain,address: str):
    try:
        WalletCreate(address=address,chain=chain)
        entities,sources,records=await repo.attribution_catalog()
        return AttributionEngine(entities,sources,records).resolve(chain,address)
    except ValueError: raise HTTPException(422,"Invalid address")
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/attributions",response_model=list[NearestEntityResult])
async def case_attributions(case_id: str):
    case=await get_case(case_id)
    if not case.latest_trace: return []
    try:
        entities,sources,records=await repo.attribution_catalog()
        return NearestEntityResolver(AttributionEngine(entities,sources,records)).resolve(case.latest_trace)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/primary-path")
async def case_primary_path(case_id: str):
    case = await get_case(case_id)
    if not case.latest_trace:
        return {"status": "UNATTRIBUTED", "root_address": next((item.address for item in case.wallets), ""), "node_ids": [], "transaction_hashes": [], "edge_ids": [], "hops": 0, "transaction_count": 0, "total_transferred_value": "UNKNOWN", "path_duration_seconds": None, "terminal_address": None, "terminal_entity_id": None, "terminal_entity_name": "UNKNOWN / UNATTRIBUTED DESTINATION", "terminal_entity_type": "UNKNOWN", "terminal_role": "UNKNOWN", "attribution": "UNKNOWN", "why": "No persisted trace is available.", "evidence_ids": [], "attribution_records": []}
    try:
        entities, sources, records = await repo.attribution_catalog()
        if is_synthetic_trace(case.latest_trace):
            entities, sources, records = merge_synthetic_attribution(entities, sources, records)
        return select_primary_path(case.latest_trace, entities, sources, records)
    except DatabaseError as exc:
        return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/entities", response_model=list[Entity])
async def case_entities(case_id: str):
    await get_case(case_id)
    try: return await repo.case_entities(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/entities/{entity_id}", response_model=Entity)
async def case_entity(case_id: str, entity_id: str):
    await get_case(case_id)
    try:
        entity=next((item for item in await repo.case_entities(case_id) if item.entity_id==entity_id), None)
        if not entity: raise HTTPException(404, "Entity is not observed in this case")
        return entity
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/wallets/{wallet_id}/entities", response_model=list[Entity])
async def wallet_entities(wallet_id: str):
    try: return await repo.wallet_entities(wallet_id)
    except DatabaseError as exc: return database_failure(exc)

def database_failure(exc: DatabaseError):
    logging.getLogger("crypto_fraud_intelligence").error("database_error",extra={"error_type":type(exc).__name__})
    raise HTTPException(503,"Persistent storage is unavailable") from exc

@app.post("/api/v1/cases",response_model=InvestigationCase)
async def create_case(body: CaseCreate):
    try:
        result=await repo.create(body); await repo.set_workflow_stage(result.case_id,CaseWorkflowStage.NEW); logging.getLogger("crypto_fraud_intelligence").info("case_created",extra={"case_id":result.case_id}); return await repo.get(result.case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases",response_model=list[CaseListItem])
async def list_cases():
    try: return await repo.list_cases()
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/dev/seed-case")
async def seed_development_case():
    root = "0x1111111111111111111111111111111111111111"
    case = await repo.create(CaseCreate(title="RRR Development Fixture Investigation", fraud_type="Investment fraud", priority="HIGH", external_case_reference="DEVELOPMENT-FIXTURE"))
    await repo.add_wallet(case.case_id, WalletCreate(address=root, chain=Chain.ETHEREUM))
    dev_tracer = TraceService(fixture_provider, fixture_registry)
    trace = await dev_tracer.trace(case.case_id, TraceRequest(address=root, chain=Chain.ETHEREUM, max_hops=3, max_nodes=100, max_edges=500, max_transactions=500))
    await repo.persist_trace(trace)
    await graph_projection.project(trace)
    await repo.set_workflow_stage(case.case_id, CaseWorkflowStage.TRACE_ANALYZED, provider=trace.provider, result_count=trace.metrics.edge_count, evidence_ids=[item.evidence_id for item in trace.evidence])
    # Attribution resolution is synchronous; it only evaluates the already
    # persisted/in-memory trace and does not perform I/O.
    attributions = NearestEntityResolver(AttributionEngine([], [], [])).resolve(trace)
    patterns = await pattern_service.analyze(trace, PatternAnalyzeRequest(trace_id=trace.trace_id), attributions)
    await repo.set_workflow_stage(case.case_id, CaseWorkflowStage.PATTERNS_ANALYZED, provider="PatternEngine", result_count=len(patterns), evidence_ids=list(dict.fromkeys(e for item in patterns for e in item.evidence_ids)))
    assessment = await risk_service.assess(case.case_id, RiskAssessRequest(trace_id=trace.trace_id))
    await repo.set_workflow_stage(case.case_id, CaseWorkflowStage.RISK_ASSESSED, provider="RuleBasedRiskEngine", result_count=len(assessment.factors), evidence_ids=assessment.evidence_ids)
    watch = await realtime_service.create_watch(case.case_id, WatchCreate(address=root, chain=Chain.ETHEREUM, source="SIMULATED"))
    await repo.set_workflow_stage(case.case_id, CaseWorkflowStage.WATCHING, provider=watch.provider)
    event = RealtimeEvent(event_id=str(uuid4()), provider="SIMULATED EVENT SOURCE", chain=Chain.ETHEREUM, received_at=datetime.now(timezone.utc), observed_at=datetime.now(timezone.utc), block_number=22000099, transaction_hash="0x" + "f" * 64, from_address=root, to_address="0x5555555555555555555555555555555555555555", asset="ETH", amount="0.25")
    event_results = await realtime_service.receive_simulated(event)
    report = await report_service.generate(case.case_id, ReportCreateRequest(trace_id=trace.trace_id))
    await repo.set_workflow_stage(case.case_id, CaseWorkflowStage.REPORT_READY, provider="ReportService", result_count=len(report.evidence_ids), evidence_ids=report.evidence_ids)
    def _safe(v):
        if isinstance(v, datetime): return v.isoformat()
        if hasattr(v, 'model_dump'): return v.model_dump(mode='json')
        return v
    return JSONResponse(content={
        "mode": str(DataMode.DEVELOPMENT_FIXTURE),
        "case_id": case.case_id,
        "trace_id": trace.trace_id,
        "watch_id": watch.watch_id,
        "report_id": report.report_id,
        "flags": [{"type": p.pattern_type, "severity": p.severity, "confidence": p.confidence_level, "pattern_id": p.pattern_id} for p in patterns],
        "counts": {"nodes": trace.metrics.node_count, "edges": trace.metrics.edge_count, "patterns": len(patterns), "risk_score": _safe(assessment.score), "realtime_results": len(event_results)},
        "note": "All records were created through PostgreSQL-backed workflows; fixture data is not live blockchain data. Flags are analytical observations, not criminality determinations."
    })

@app.post("/api/v1/dev/demo/start")
async def start_development_demo():
    """One-click lab demo: create a real persisted fixture case, then stream it."""
    result=await seed_development_case()
    await synthetic_engine.configure(result["case_id"],"MULTI_STAGE_FRAUD","rrr-demo-2026",2.0,20)
    status=await synthetic_engine.start()
    return {"mode":"DEVELOPMENT_SYNTHETIC","case_id":result["case_id"],"trace_id":result["trace_id"],"seed":result,"engine":status}

@app.post("/api/v1/dev/synthetic/cases")
async def generate_synthetic_case(body: SyntheticCaseRequest):
    """Create a fixture-backed case and persist an exact synthetic event volume for lab investigation."""
    result = await seed_development_case()
    await synthetic_engine.stop()
    await synthetic_engine.configure(result["case_id"], body.scenario, body.scenario_seed, 2.0, body.event_count)
    batch = await synthetic_engine.run_batch(body.event_count)
    integrity = await repo.database_integrity()
    return {**result, "mode":"DEVELOPMENT_SYNTHETIC", "synthetic": {"scenario":body.scenario.upper(),"seed":body.scenario_seed,"requested_events":body.event_count,"processed_events":batch["processed_events"]}, "integrity":integrity, "note":"All generated records are DEVELOPMENT_SYNTHETIC and were normalized, persisted, graph-projected, assessed, evidenced, and placed on the case timeline through the normal realtime pipeline."}

@app.get("/api/v1/dev/fixture/status")
async def development_fixture_status():
    return {"mode": settings.blockchain_data_mode.upper(), "provider": fixture_provider.name, "root_address": "0x1111111111111111111111111111111111111111", "available": True}

@app.delete("/api/v1/dev/seed-case/{case_id}")
async def delete_development_case(case_id: str):
    try:
        if not await repo.delete_case(case_id): raise HTTPException(404, "Case not found")
        return {"deleted": True, "case_id": case_id}
    except DatabaseError as exc: return database_failure(exc)

@app.patch("/api/v1/cases/{case_id}",response_model=InvestigationCase)
async def update_case(case_id: str, body: CasePatch):
    try:
        result=await repo.update_case(case_id,body)
        if not result: raise HTTPException(404,"Case not found")
        await repo.append_audit_event(AuditEvent(event_id=str(uuid4()),case_id=case_id,action="CASE_UPDATED",resource_type="CASE",resource_id=case_id,occurred_at=datetime.now(timezone.utc),metadata={"fields":list(body.model_dump(exclude_unset=True))}))
        return result
    except ValueError: raise HTTPException(404,"Case not found")
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/close",response_model=InvestigationCase)
async def close_case(case_id: str):
    try:
        result=await repo.close_case(case_id)
        if not result: raise HTTPException(404,"Case not found")
        return result
    except ValueError: raise HTTPException(404,"Case not found")
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/reopen",response_model=InvestigationCase)
async def reopen_case(case_id: str):
    try:
        result=await repo.reopen_case(case_id)
        if not result: raise HTTPException(404,"Case not found")
        return result
    except ValueError: raise HTTPException(404,"Case not found")
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/status",response_model=InvestigationCase)
async def set_case_status(case_id: str, body: dict):
    status = str(body.get("status", "")).upper()
    if status not in {"OPEN", "INVESTIGATING", "CLOSED"}:
        raise HTTPException(422, "status must be OPEN, INVESTIGATING, or CLOSED")
    try:
        result = await repo._set_case_status(case_id, status)
        if not result: raise HTTPException(404, "Case not found")
        return result
    except ValueError: raise HTTPException(404, "Case not found")
    except DatabaseError as exc: return database_failure(exc)

# New endpoint to open a case directly
@app.post("/api/v1/cases/{case_id}/open",response_model=InvestigationCase)
async def open_case(case_id: str):
    """Convenience endpoint to set a case status to OPEN.
    Calls the existing status update logic with status='OPEN'."""
    try:
        result = await repo._set_case_status(case_id, "OPEN")
        if not result:
            raise HTTPException(404, "Case not found")
        return result
    except ValueError:
        raise HTTPException(404, "Case not found")
    except DatabaseError as exc:
        return database_failure(exc)

async def get_case(case_id: str):
    try: result=await repo.get(case_id)
    except DatabaseError as exc: return database_failure(exc)
    if not result: raise HTTPException(404,"Case not found")
    return result

@app.post("/api/v1/cases/{case_id}/wallets",response_model=InvestigationCase)
async def add_wallet(case_id: str, body: WalletCreate):
    try:
        result=await repo.add_wallet(case_id,body)
        if not result: raise HTTPException(404,"Case not found")
        logging.getLogger("crypto_fraud_intelligence").info("wallet_added",extra={"case_id":case_id,"chain":body.chain}); return await repo.set_workflow_stage(case_id,CaseWorkflowStage.INTAKE_COMPLETE) or result
    except ValueError: raise HTTPException(404,"Case not found")
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/transactions",response_model=InvestigationCase)
async def add_transaction(case_id: str, body: TransactionCreate):
    try:
        result=await repo.add_transaction(case_id,body)
        if not result: raise HTTPException(404,"Case not found")
        logging.getLogger("crypto_fraud_intelligence").info("transaction_ingested",extra={"case_id":case_id,"tx_hash":body.tx_hash}); return result
    except ValueError: raise HTTPException(404,"Case not found")
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}",response_model=InvestigationCase)
async def read_case(case_id: str):
    logging.getLogger("crypto_fraud_intelligence").info("CASE OPEN case_id=%s", case_id)
    return await get_case(case_id)

@app.get("/api/v1/cases/{case_id}/transactions",response_model=list[CaseTransactionView])
async def case_transactions(case_id: str, limit: int = 500, offset: int = 0, chain: str | None = None, asset: str | None = None, status: str | None = None, wallet: str | None = None, direction: str | None = None, search: str | None = None, start: datetime | None = None, end: datetime | None = None):
    logging.getLogger("crypto_fraud_intelligence").info("CASE TRANSACTIONS case_id=%s limit=%s", case_id, limit)
    await get_case(case_id)
    try: return await repo.case_transactions(case_id, limit, offset, chain, asset, status, wallet, direction, search, start, end)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/summary",response_model=CaseSummarySnapshot)
async def case_summary(case_id: str):
    try:
        case=await get_case(case_id)
        return await _case_summary_snapshot(case)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/wallets/{chain}/{address}",response_model=WalletIntelligence)
async def wallet_intelligence(chain: str, address: str):
    try:
        selected_chain=Chain(chain.lower())
        normalized=normalize_address(selected_chain,address)
        WalletCreate(address=normalized,chain=selected_chain)
        result=await repo.wallet_intelligence(selected_chain,normalized)
        if not result: raise HTTPException(404,"Wallet has no persisted investigation record")
        return result
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/evidence",response_model=list[Evidence])
async def case_evidence(case_id: str):
    await get_case(case_id)
    try: return await repo.list_evidence(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/evidence", response_model=list[Evidence])
async def all_evidence():
    try: return await repo.list_all_evidence()
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/evidence/{evidence_id}", response_model=Evidence)
async def read_evidence(evidence_id: str):
    try:
        result = await repo.get_evidence(evidence_id)
        if not result: raise HTTPException(404, "Evidence not found")
        return result
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/evidence/manifest",response_model=EvidenceManifest)
async def create_evidence_manifest(case_id: str, body: EvidenceManifestRequest = EvidenceManifestRequest()):
    try: return await evidence_service.create_manifest(case_id, body)
    except ValueError as exc: raise HTTPException(422 if "evidence" in str(exc).lower() else 404, str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/evidence/ledger",response_model=list[EvidenceLedgerEntry])
async def evidence_ledger(case_id: str):
    await get_case(case_id)
    try: return await evidence_service.ledger_entries(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/evidence/manifests",response_model=list[EvidenceManifest])
async def evidence_manifests(case_id: str):
    await get_case(case_id)
    try: return await evidence_service.manifests(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/evidence/{evidence_id}/chain-of-custody",response_model=list[EvidenceChainEvent])
async def evidence_chain_of_custody(case_id: str, evidence_id: str):
    await get_case(case_id)
    try: return await evidence_service.chain(case_id, evidence_id)
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/reports", response_model=InvestigationReport)
async def create_report(case_id: str, body: ReportCreateRequest = ReportCreateRequest()):
    try:
        result=await report_service.generate(case_id, body); await repo.set_workflow_stage(case_id,CaseWorkflowStage.REPORT_READY,provider="ReportService",result_count=len(result.evidence_ids),evidence_ids=result.evidence_ids); return result
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/reports", response_model=list[InvestigationReport])
async def list_reports(case_id: str):
    await get_case(case_id)
    try: return await report_service.list(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/reports/{report_id}", response_model=InvestigationReport)
async def get_report(case_id: str, report_id: str):
    await get_case(case_id)
    try:
        result = await report_service.get(case_id, report_id)
        if not result: raise HTTPException(404, "Report not found")
        return result
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/reports/{report_id}/pdf")
async def download_report_pdf(case_id: str, report_id: str):
    await get_case(case_id)
    try:
        result = await report_service.get(case_id, report_id)
        if not result:
            raise HTTPException(404, "Report not found")
        pdf = render_report_pdf(result)
        filename = f"crypto-fraud-report-{case_id[:8]}-{report_id[:8]}.pdf"
        return StreamingResponse(iter([pdf]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Length": str(len(pdf))})
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/traces",response_model=TraceResult)
async def trace_case(case_id: str, body: TraceRequest):
    await get_case(case_id)
    try:
        logging.getLogger("crypto_fraud_intelligence").info("trace_started",extra={"case_id":case_id,"address":body.address.lower()})
        await repo.set_workflow_stage(case_id,CaseWorkflowStage.DATA_ACQUISITION,provider=body.chain.value)
        result=await tracer.trace(case_id,body); await repo.persist_trace(result); await graph_projection.project(result); await repo.set_workflow_stage(case_id,CaseWorkflowStage.TRACE_ANALYZED,provider=result.provider,result_count=result.metrics.edge_count,evidence_ids=[item.evidence_id for item in result.evidence]); return result
    except ProviderError as exc:
        logging.getLogger("crypto_fraud_intelligence").error("provider_error",extra={"case_id":case_id})
        raise HTTPException(502,str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/traces",response_model=list[TraceResult])
async def list_traces(case_id: str):
    await get_case(case_id)
    try: return await repo.list_traces(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/graph",response_model=TraceResult)
async def read_graph(case_id: str):
    case=await get_case(case_id)
    if not case.latest_trace: raise HTTPException(404,"No persisted graph for case")
    return case.latest_trace

@app.get("/api/v1/cases/{case_id}/graph/paths")
async def graph_paths(case_id: str):
    case=await get_case(case_id)
    if not case.latest_trace: raise HTTPException(404,"No persisted graph for case")
    return {"trace_id":case.latest_trace.trace_id,"paths":case.latest_trace.paths}

@app.get("/api/v1/cases/{case_id}/graph/metrics")
async def graph_metrics(case_id: str):
    case=await get_case(case_id)
    if not case.latest_trace: raise HTTPException(404,"No persisted graph for case")
    return {"trace_id":case.latest_trace.trace_id,"metrics":case.latest_trace.metrics}

@app.get("/api/v1/cases/{case_id}/graph/layout", response_model=GraphLayout)
async def get_graph_layout(case_id: str):
    await get_case(case_id)
    try: return await repo.graph_layout(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/graph/layout", response_model=GraphLayout)
async def save_graph_layout(case_id: str, body: GraphLayoutUpdate):
    await get_case(case_id)
    if len(body.node_positions) > 5000: raise HTTPException(422, "At most 5000 node positions may be saved")
    try: return await repo.save_graph_layout(case_id, body)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/traces/{trace_id}",response_model=TraceResult)
async def read_trace(case_id: str, trace_id: str):
    await get_case(case_id)
    try:
        result=await repo.get_trace(case_id,trace_id)
        if not result: raise HTTPException(404,"Trace not found")
        return result
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/graph/{case_id}/project", response_model=GraphProjectionStatus)
async def project_case_graph(case_id: str):
    case=await get_case(case_id)
    if not case.latest_trace: raise HTTPException(404,"No persisted trace for case")
    if graph_client.status != CapabilityStatus.SUPPORTED:
        return graph_projection.status()
    await graph_projection.project(case.latest_trace)
    return graph_projection.status()

@app.get("/api/v1/graph/{case_id}/neighbors", response_model=GraphQueryResult)
async def graph_neighbors(case_id: str, address: str, depth: int = 1):
    await get_case(case_id)
    if depth < 1 or depth > 5: raise HTTPException(422,"depth must be between 1 and 5")
    try:
        result=await graph_projection.require_repository()
        return await result.neighbors(case_id,address,depth)
    except RuntimeError as exc: raise HTTPException(503,"Neo4j graph projection is unavailable") from exc

@app.get("/api/v1/graph/{case_id}/shortest-path", response_model=GraphQueryResult)
async def graph_shortest_path(case_id: str, source: str, destination: str):
    await get_case(case_id)
    try:
        result=await graph_projection.require_repository()
        return await result.shortest_path(case_id,source,destination)
    except RuntimeError as exc: raise HTTPException(503,"Neo4j graph projection is unavailable") from exc

async def _trace_for_patterns(case_id: str, trace_id: str | None):
    case=await get_case(case_id)
    if trace_id:
        result=await repo.get_trace(case_id,trace_id)
        if not result: raise HTTPException(404,"Trace not found")
        return result
    if not case.latest_trace: raise HTTPException(404,"No persisted trace for case")
    return case.latest_trace

async def _case_attributions(trace: TraceResult):
    try:
        entities,sources,records=await repo.attribution_catalog()
        if is_synthetic_trace(trace):
            entities,sources,records=merge_synthetic_attribution(entities,sources,records)
        return NearestEntityResolver(AttributionEngine(entities,sources,records)).resolve(trace)
    except Exception as exc:
        logging.getLogger("crypto_fraud_intelligence").warning(
            "attribution_catalog_error",
            extra={"error_type": type(exc).__name__, "detail": str(exc)[:200]}
        )
        return []

async def _case_summary_snapshot(case: InvestigationCase) -> CaseSummarySnapshot:
    log = logging.getLogger("crypto_fraud_intelligence")
    log.info("CASE SUMMARY case_id=%s", case.case_id)
    counts=await repo.case_summary_counts(case.case_id)
    risk=await risk_service.latest(case.case_id)
    try:
        nearest=await _case_attributions(case.latest_trace) if case.latest_trace else []
    except Exception as exc:
        log.warning("case_summary_attribution_skipped", extra={"case_id": case.case_id, "reason": str(exc)[:200]})
        nearest = []
    vasps=[item for item in nearest if item.entity.entity_type in {EntityType.VASP,EntityType.EXCHANGE,EntityType.CUSTODIAL_SERVICE}]
    exposure={"count":len(vasps),"nearest":({"entity":vasps[0].entity.name,"entity_id":vasps[0].entity.entity_id,"hop_distance":vasps[0].hop_distance,"confidence":vasps[0].confidence,"address":vasps[0].address,"path":[edge.transaction_hash for edge in vasps[0].path.edges]} if vasps else None),"source":"CURATED INTELLIGENCE" if vasps else None}
    return CaseSummarySnapshot(case_id=case.case_id,status=case.status,workflow_stage=case.workflow_stage,risk=risk,vasp_exposure=exposure,generated_at=datetime.now(timezone.utc),**counts)

def _latest_workflow_event(events: list[dict], stage: str):
    matches=[item for item in events if item.get("stage")==stage]
    return matches[0] if matches else None

def _stage(stage: str, status: str, event: dict | None = None, *, records: int = 0, provider: str | None = None, mode: str | None = None, evidence_ids: list[str] | None = None):
    started=event.get("started_at") if event else None
    completed=event.get("completed_at") if event else None
    duration=None
    if started and completed:
        try: duration=int((completed-started).total_seconds()*1000)
        except TypeError: duration=None
    return OperationalStageState(stage=stage,status=status,started_at=started,completed_at=completed,duration_ms=duration,records_produced=records or (event.get("result_count") if event and event.get("result_count") is not None else 0),provider=provider or (event.get("provider") if event else None),mode=mode,error=event.get("error") if event else None,evidence_ids=evidence_ids or (event.get("evidence_ids") if event else []) or [])

async def _operational_state(case_id: str) -> InvestigationOperationalState:
    case=await get_case(case_id)
    summary=await _case_summary_snapshot(case)
    workflow=await repo.workflow_events(case_id)
    transactions=await repo.case_transactions(case_id, limit=500)
    entities=await repo.case_entities(case_id)
    attributions_raw = []
    try:
        attributions_raw=await _case_attributions(case.latest_trace) if case.latest_trace else []
    except Exception as exc:
        logging.getLogger("crypto_fraud_intelligence").warning(
            "operational_state_attribution_skipped case_id=%s error=%s", case_id, str(exc)[:200]
        )
    attributions = attributions_raw
    patterns=await pattern_service.list(case_id, case.latest_trace.trace_id if case.latest_trace else None)
    risk=await risk_service.latest(case_id)
    watches=await realtime_service.watches(case_id)
    alerts=await repo.alerts(case_id)
    evidence=await repo.list_evidence(case_id)
    reports=await report_service.list(case_id)
    event_for=lambda stage: _latest_workflow_event(workflow, stage)
    mode=case.latest_trace.mode if case.latest_trace else settings.blockchain_data_mode.upper()
    stages=[
        _stage("INTAKE","COMPLETED",records=1,mode=mode),
        _stage("CASE_CREATED","COMPLETED",event_for(CaseWorkflowStage.NEW),records=1,mode=mode),
        _stage("WALLET_REGISTERED","COMPLETED" if summary.wallets else "PENDING",records=summary.wallets,mode=mode),
        _stage("DATA_ACQUISITION","COMPLETED" if case.latest_trace else ("FAILED" if event_for(CaseWorkflowStage.DATA_ACQUISITION) and event_for(CaseWorkflowStage.DATA_ACQUISITION).get("error") else "PENDING"),event_for(CaseWorkflowStage.DATA_ACQUISITION),records=summary.transactions,mode=mode),
        _stage("NORMALIZATION","COMPLETED" if summary.transactions else "PENDING",records=summary.transactions,provider=case.latest_trace.provider if case.latest_trace else None,mode=mode,evidence_ids=[item.evidence_id for item in evidence]),
        _stage("LEDGER_BUILT","COMPLETED" if summary.transactions else "PENDING",records=summary.transactions,mode=mode),
        _stage("GRAPH_BUILT","COMPLETED" if summary.graph_edges else "PENDING",event_for(CaseWorkflowStage.TRACE_ANALYZED),records=summary.graph_edges,provider="PostgreSQL/Neo4j projection",mode=mode),
        _stage("ENTITY_ATTRIBUTION","COMPLETED" if attributions else ("UNKNOWN" if case.latest_trace else "PENDING"),records=len(attributions),provider="Curated attribution catalog",mode=mode,evidence_ids=list(dict.fromkeys(e.evidence_id for item in attributions for e in item.evidence))),
        _stage("FUND_FLOW_ANALYSIS","COMPLETED" if case.latest_trace else "PENDING",records=case.latest_trace.metrics.path_count if case.latest_trace else 0,mode=mode),
        _stage("PATTERN_ANALYSIS","COMPLETED" if patterns else "PENDING",event_for(CaseWorkflowStage.PATTERNS_ANALYZED),records=len(patterns),provider="PatternEngine",mode=mode,evidence_ids=list(dict.fromkeys(e for item in patterns for e in item.evidence_ids))),
        _stage("RISK_ASSESSMENT","COMPLETED" if risk else "PENDING",event_for(CaseWorkflowStage.RISK_ASSESSED),records=len(risk.factors) if risk else 0,provider="RuleBasedRiskEngine",mode=mode,evidence_ids=risk.evidence_ids if risk else []),
        _stage("REALTIME_WATCH","COMPLETED" if watches else "PENDING",event_for(CaseWorkflowStage.WATCHING),records=len(watches),mode=mode),
        _stage("EVENT_RECEIVED","COMPLETED" if summary.realtime_events else "PENDING",records=summary.realtime_events,provider="RealtimeService",mode=mode),
        _stage("GRAPH_UPDATED","COMPLETED" if summary.graph_edges else "PENDING",records=summary.graph_edges,provider="GraphProjection",mode=mode),
        _stage("RISK_REASSESSED","COMPLETED" if risk and summary.realtime_events else ("PENDING" if not risk else "PARTIAL"),records=1 if risk else 0,provider="RuleBasedRiskEngine",mode=mode),
        _stage("ALERT_GENERATED","COMPLETED" if alerts else "PENDING",event_for(CaseWorkflowStage.ALERTED),records=len(alerts),mode=mode,evidence_ids=list(dict.fromkeys(e for item in alerts for e in item.evidence_ids))),
        _stage("EVIDENCE_REVIEW","COMPLETED" if evidence else "PENDING",records=len(evidence),provider="EvidenceLedger",mode=mode,evidence_ids=[item.evidence_id for item in evidence[:20]]),
        _stage("INVESTIGATOR_ACTION","PARTIAL" if any(item.get("stage")==CaseWorkflowStage.UNDER_REVIEW for item in workflow) else "PENDING",event_for(CaseWorkflowStage.UNDER_REVIEW),mode=mode),
        _stage("REPORT_GENERATED","COMPLETED" if reports else "PENDING",event_for(CaseWorkflowStage.REPORT_READY),records=len(reports),provider="ReportService",mode=mode,evidence_ids=list(dict.fromkeys(e for item in reports for e in item.evidence_ids))),
        _stage("CLOSED","COMPLETED" if case.status=="CLOSED" else "PENDING",records=1 if case.status=="CLOSED" else 0,mode=mode),
    ]
    graph_backend="Neo4j + PostgreSQL" if graph_client.status == CapabilityStatus.SUPPORTED else "PostgreSQL"
    return InvestigationOperationalState(case=case,summary=summary,stages=stages,workflow_events=workflow,transactions=transactions,entities=entities,attributions=attributions,patterns=patterns,risk=risk,watches=watches,alerts=alerts,evidence=evidence,reports=reports,graph_backend=graph_backend,generated_at=datetime.now(timezone.utc))

@app.get("/api/v1/cases/{case_id}/operational-state", response_model=InvestigationOperationalState)
async def case_operational_state(case_id: str):
    logging.getLogger("crypto_fraud_intelligence").info("CASE OPERATIONAL STATE case_id=%s", case_id)
    try: return await _operational_state(case_id)
    except DatabaseError as exc: return database_failure(exc)

async def _run_investigation(case_id: str, body: InvestigationRunRequest) -> InvestigationOperationalState:
    case=await get_case(case_id)
    address=body.address or (case.wallets[0].address if case.wallets else None)
    if not address: raise HTTPException(422,"Add a reported wallet or provide address before running investigation")
    WalletCreate(address=address,chain=body.chain)
    if not any(item.address.lower()==normalize_address(body.chain,address).lower() and item.chain==body.chain for item in case.wallets):
        await repo.add_wallet(case_id,WalletCreate(address=address,chain=body.chain))
    try:
        await repo._set_case_status(case_id,"INVESTIGATING")
        trace=await trace_case(case_id,TraceRequest(address=address,chain=body.chain,direction=body.direction,max_hops=body.max_hops,max_nodes=body.max_nodes,max_edges=body.max_edges,max_transactions=body.max_transactions))
        attributions=await _case_attributions(trace)
        
        targets = {(node.chain, node.address) for node in trace.nodes}
        targets.add((body.chain, address))
        records = await repo.sanctions_records()
        sanctions_provider = CuratedSanctionsProvider(records, configured=bool(records))
        for ch, addr in targets:
            screening_result = await sanctions_provider.screen_address(ch, addr)
            await repo.persist_screening(case_id, screening_result)

        await repo.set_workflow_stage(case_id,CaseWorkflowStage.TRACE_ANALYZED,provider=f"{trace.provider} + attribution + sanctions",result_count=len(attributions),evidence_ids=list(dict.fromkeys(e.evidence_id for item in attributions for e in item.evidence)))
        patterns=await pattern_service.analyze(trace,PatternAnalyzeRequest(trace_id=trace.trace_id),attributions)
        await repo.set_workflow_stage(case_id,CaseWorkflowStage.PATTERNS_ANALYZED,provider="PatternEngine",result_count=len(patterns),evidence_ids=list(dict.fromkeys(e for item in patterns for e in item.evidence_ids)))
        assessment=await risk_service.assess(case_id,RiskAssessRequest(trace_id=trace.trace_id))
        await repo.set_workflow_stage(case_id,CaseWorkflowStage.RISK_ASSESSED,provider="RuleBasedRiskEngine",result_count=len(assessment.factors),evidence_ids=assessment.evidence_ids)
        if body.start_watch:
            await realtime_service.create_watch(case_id,WatchCreate(address=address,chain=body.chain,source="INVESTIGATOR"))
            await repo.set_workflow_stage(case_id,CaseWorkflowStage.WATCHING,provider=realtime_provider.name)
        if body.create_report:
            report=await report_service.generate(case_id,ReportCreateRequest(trace_id=trace.trace_id,created_by="investigator-session"))
            await repo.set_workflow_stage(case_id,CaseWorkflowStage.REPORT_READY,provider="ReportService",result_count=len(report.evidence_ids),evidence_ids=report.evidence_ids)
        await repo.append_timeline(TimelineEvent(
            event_id=str(uuid4()),
            case_id=case_id,
            timestamp=datetime.now(timezone.utc),
            event_type="INVESTIGATION_COMPLETED",
            summary="Normal investigation pipeline completed through persisted trace, graph, attribution, pattern, risk, and watch stages.",
            source="InvestigationOrchestrator",
            evidence_ids=list(dict.fromkeys(e.evidence_id for item in attributions for e in item.evidence)),
            metadata={"trace_id": trace.trace_id, "pattern_count": len(patterns), "risk_assessment_id": assessment.assessment_id, "watch_started": body.start_watch, "report_created": body.create_report},
        ))
        return await _operational_state(case_id)
    except ProviderError as exc:
        await repo.set_workflow_stage(case_id,CaseWorkflowStage.DATA_ACQUISITION,provider=body.chain.value,error=str(exc))
        raise HTTPException(502,str(exc)) from exc

@app.post("/api/v1/cases/{case_id}/investigate", response_model=InvestigationOperationalState)
async def investigate_case(case_id: str, body: InvestigationRunRequest = InvestigationRunRequest()):
    try: return await _run_investigation(case_id, body)
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/investigate/{stage}/retry", response_model=InvestigationOperationalState)
async def retry_investigation_stage(case_id: str, stage: str, body: InvestigationRunRequest = InvestigationRunRequest()):
    if stage.upper() not in {"DATA_ACQUISITION","NORMALIZATION","LEDGER_BUILT","GRAPH_BUILT","ENTITY_ATTRIBUTION","FUND_FLOW_ANALYSIS","PATTERN_ANALYSIS","RISK_ASSESSMENT","REALTIME_WATCH","REPORT_GENERATED"}:
        raise HTTPException(422,"Unsupported retry stage")
    try: return await _run_investigation(case_id, body)
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/patterns/analyze",response_model=list[PatternObservation])
async def analyze_patterns(case_id: str, body: PatternAnalyzeRequest = PatternAnalyzeRequest()):
    try:
        trace=await _trace_for_patterns(case_id,body.trace_id)
        attributions=await _case_attributions(trace)
        result=await pattern_service.analyze(trace,body,attributions); await repo.set_workflow_stage(case_id,CaseWorkflowStage.PATTERNS_ANALYZED,provider="PatternEngine",result_count=len(result),evidence_ids=list(dict.fromkeys(e for item in result for e in item.evidence_ids))); return result
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/patterns/summary",response_model=PatternSummary)
async def pattern_summary(case_id: str, trace_id: str | None = None):
    await get_case(case_id)
    try: return await pattern_service.summary(case_id,trace_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/patterns",response_model=list[PatternObservation])
async def list_patterns(case_id: str, trace_id: str | None = None):
    await get_case(case_id)
    try: return await pattern_service.list(case_id,trace_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/patterns/{pattern_id}",response_model=PatternObservation)
async def read_pattern(case_id: str, pattern_id: str):
    await get_case(case_id)
    try:
        result=await pattern_service.get(case_id,pattern_id)
        if not result: raise HTTPException(404,"Pattern observation not found")
        return result
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/traces/{trace_id}/patterns",response_model=list[PatternObservation])
async def list_trace_patterns(trace_id: str):
    try:
        return await pattern_service.list_by_trace(trace_id)
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/risk/assess",response_model=RiskAssessment)
async def assess_case_risk(case_id: str, body: RiskAssessRequest = RiskAssessRequest()):
    try:
        result=await risk_service.assess(case_id,body); await repo.set_workflow_stage(case_id,CaseWorkflowStage.RISK_ASSESSED,provider="RuleBasedRiskEngine",result_count=len(result.factors),evidence_ids=result.evidence_ids); return result
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/risk",response_model=RiskAssessment|None)
async def current_case_risk(case_id: str, subject_id: str | None = None):
    await get_case(case_id)
    try: return await risk_service.latest(case_id,subject_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/risk/history",response_model=list[RiskAssessment])
async def case_risk_history(case_id: str, subject_id: str | None = None):
    await get_case(case_id)
    try: return await risk_service.history(case_id,subject_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/risk/delta",response_model=RiskDelta|None)
async def case_risk_delta(case_id: str, subject_id: str | None = None):
    await get_case(case_id)
    try: return await risk_service.delta(case_id,subject_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/risk/factors",response_model=list[RiskFactor])
async def case_risk_factors(case_id: str, assessment_id: str | None = None):
    await get_case(case_id)
    try: return await risk_service.factors(case_id,assessment_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/risk/alerts",response_model=list[RiskAlertCandidate])
async def case_risk_alerts(case_id: str, subject_id: str | None = None):
    await get_case(case_id)
    try: return await risk_service.alerts(case_id,subject_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/wallets/{wallet_id}/risk",response_model=list[RiskAssessment])
async def wallet_risk(wallet_id: str):
    try: return await risk_service.wallet(wallet_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/traces/{trace_id}/risk",response_model=list[RiskAssessment])
async def trace_risk(trace_id: str):
    try: return await risk_service.trace(trace_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/realtime/capabilities", response_model=list[ProviderCapability])
async def realtime_capabilities():
    return realtime_service.capabilities()

@app.get("/api/v1/realtime/health")
async def realtime_health():
    return await realtime_service.health()

@app.post("/api/v1/cases/{case_id}/watches", response_model=WatchTarget)
async def create_watch(case_id: str, body: WatchCreate):
    try:
        result=await realtime_service.create_watch(case_id,body)
        await repo.set_workflow_stage(case_id,CaseWorkflowStage.WATCHING,provider=result.provider)
        logging.getLogger("crypto_fraud_intelligence").info("watch_started",extra={"case_id":case_id,"watch_id":result.watch_id,"status":result.status})
        return result
    except ValueError as exc: raise HTTPException(404 if str(exc) == "Case not found" else 409,str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/watches", response_model=list[WatchTarget])
async def list_watches(case_id: str):
    await get_case(case_id)
    try: return await realtime_service.watches(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/watches/{watch_id}/pause", response_model=WatchTarget)
async def pause_watch(case_id: str, watch_id: str):
    try: return await realtime_service.set_status(case_id,watch_id,WatchTargetStatus.PAUSED)
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/watches/{watch_id}/resume", response_model=WatchTarget)
async def resume_watch(case_id: str, watch_id: str):
    try: return await realtime_service.set_status(case_id,watch_id,WatchTargetStatus.ACTIVE)
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.delete("/api/v1/cases/{case_id}/watches/{watch_id}", response_model=WatchTarget)
async def stop_watch(case_id: str, watch_id: str):
    try: return await realtime_service.set_status(case_id,watch_id,WatchTargetStatus.STOPPED)
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/realtime/providers/alchemy/webhook")
async def alchemy_webhook(request: Request):
    raw=await request.body()
    if len(raw)>settings.realtime_max_payload_bytes: raise HTTPException(413,"Webhook payload is too large")
    signature=request.headers.get("x-alchemy-signature")
    try: payload=json.loads(raw)
    except json.JSONDecodeError as exc: raise HTTPException(400,"Malformed webhook JSON") from exc
    try: return {"mode":DataMode.WEBHOOK,"events":await realtime_service.receive_webhook(payload,raw,signature)}
    except PermissionError as exc: raise HTTPException(401,str(exc)) from exc
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/realtime/simulated/events")
async def simulated_realtime_event(body: RealtimeEvent):
    try: return {"mode":DataMode.SIMULATED,"results":await realtime_service.receive_simulated(body)}
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/realtime/stream")
async def realtime_stream(request: Request, case_id: str | None = None, last_event_id: str | None = None):
    async def encode():
        async for item in event_bus.subscribe(case_id,last_event_id):
            if await request.is_disconnected(): break
            yield f"id: {item['event_id']}\nevent: {item['event_type']}\ndata: {json.dumps(item,default=str)}\n\n"
    return StreamingResponse(encode(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})

@app.get("/api/v1/realtime/stream/status")
async def realtime_stream_status(): return {"status":"CONNECTED","mode":settings.blockchain_data_mode.upper(),**event_bus.status()}

async def _configure_synthetic(body: dict, scenario: str | None = None):
    case_id=body.get("case_id") or synthetic_engine.case_id
    if not case_id: raise HTTPException(422,"case_id is required before starting the synthetic engine")
    await synthetic_engine.configure(case_id, scenario or body.get("scenario","ESCALATION"), str(body.get("scenario_seed",body.get("seed","rrr-phase-9a"))), float(body.get("interval_seconds",2.0)), int(body.get("maximum_events",100)))

@app.post("/api/v1/dev/realtime/start")
async def start_synthetic_realtime(body: dict = {}):
    try:
        if not synthetic_engine.case_id or (body.get("case_id") and body.get("case_id") != synthetic_engine.case_id) or (body.get("scenario") and body.get("scenario").upper() != synthetic_engine.scenario) or (body.get("scenario_seed",body.get("seed")) and body.get("scenario_seed",body.get("seed")) != synthetic_engine.seed): await _configure_synthetic(body)
        return await synthetic_engine.start()
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc

@app.post("/api/v1/dev/realtime/stop")
async def stop_synthetic_realtime(): return await synthetic_engine.stop()

@app.post("/api/v1/dev/realtime/pause")
async def pause_synthetic_realtime(): return await synthetic_engine.pause()

@app.post("/api/v1/dev/realtime/resume")
async def resume_synthetic_realtime():
    try: return await synthetic_engine.resume()
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc

@app.post("/api/v1/dev/realtime/step")
async def step_synthetic_realtime(body: dict = {}):
    try:
        if not synthetic_engine.case_id or (body.get("case_id") and body.get("case_id") != synthetic_engine.case_id) or (body.get("scenario") and body.get("scenario").upper() != synthetic_engine.scenario) or (body.get("scenario_seed",body.get("seed")) and body.get("scenario_seed",body.get("seed")) != synthetic_engine.seed): await _configure_synthetic(body)
        return await synthetic_engine.step()
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc

@app.get("/api/v1/dev/realtime/status")
async def synthetic_realtime_status(): return synthetic_engine.status()

@app.get("/api/v1/dev/realtime/events")
async def synthetic_realtime_events(limit: int = 50):
    if limit < 1 or limit > 500: raise HTTPException(422,"limit must be between 1 and 500")
    try: return {"mode":"DEVELOPMENT_SYNTHETIC","events":await synthetic_engine.events(limit)}
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/dev/realtime/scenarios/{scenario}/start")
async def start_synthetic_scenario(scenario: str, body: dict = {}):
    try:
        await _configure_synthetic(body, scenario)
        return await synthetic_engine.start()
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc

@app.get("/api/v1/realtime/events/{event_id}", response_model=RealtimeEvent)
async def realtime_event(event_id: str):
    try:
        result=await repo.get_realtime_event(event_id)
        if not result: raise HTTPException(404,"Realtime event not found")
        return result
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/realtime/failures", response_model=list[RealtimeOperationalEvent])
async def realtime_failures(limit: int = 100):
    if limit < 1 or limit > 500: raise HTTPException(422, "limit must be between 1 and 500")
    try: return await repo.list_realtime_failures(limit)
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/realtime/events/{event_id}/replay")
async def replay_realtime_event(event_id: str):
    try: return {"results": await realtime_service.replay(event_id), "mode": DataMode.WEBHOOK}
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/timeline", response_model=list[TimelineEvent])
async def case_timeline(case_id: str):
    await get_case(case_id)
    try: return await repo.timeline(case_id)
    except DatabaseError as exc: return database_failure(exc)

# Mobile clients use these thin contracts over the same services as the web investigator UI.
# They do not receive provider credentials and never run intelligence logic on-device.
@app.get("/api/v1/mobile/investigator/feed")
async def mobile_investigator_feed(limit: int = 20):
    if limit < 1 or limit > 100: raise HTTPException(422, "limit must be between 1 and 100")
    try:
        return {"mode":settings.blockchain_data_mode.upper(),"system":await _system_dependencies(),"summary":await repo.dashboard_summary(),"cases":(await repo.list_cases())[:limit],"alerts":(await repo.all_alerts())[:limit]}
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/mobile/cases", response_model=list[CaseListItem])
async def mobile_cases(): return await list_cases()

@app.get("/api/v1/mobile/cases/{case_id}", response_model=InvestigationCase)
async def mobile_case(case_id: str): return await get_case(case_id)

@app.get("/api/v1/mobile/alerts", response_model=list[Alert])
async def mobile_alerts(): return await all_alerts()

@app.post("/api/v1/mobile/cases/{case_id}/acknowledge")
async def mobile_acknowledge_case(case_id: str, body: dict = {}):
    await get_case(case_id)
    now=datetime.now(timezone.utc); actor=str(body.get("actor_id","mobile-investigator"))[:200]
    try:
        await repo.append_audit_event(AuditEvent(event_id=str(uuid4()),case_id=case_id,action="MOBILE_CASE_ACKNOWLEDGED",resource_type="CASE",resource_id=case_id,actor_id=actor,occurred_at=now,metadata={"channel":"MOBILE"}))
        await repo.append_timeline(TimelineEvent(event_id=str(uuid4()),case_id=case_id,timestamp=now,event_type="INVESTIGATOR_ACTION",summary="Case acknowledged from a mobile investigator client.",source="MobileAPI",metadata={"actor_id":actor}))
        return {"acknowledged":True,"case_id":case_id,"timestamp":now}
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/mobile/cases/{case_id}/watch", response_model=WatchTarget)
async def mobile_watch_case(case_id: str, body: WatchCreate):
    # Development APK testing is explicit; production requests retain their requested provider boundary.
    effective = body.model_copy(update={"source":"DEVELOPMENT_SYNTHETIC"}) if settings.blockchain_data_mode.upper() == "DEVELOPMENT_FIXTURE" and body.source == "MOBILE_API" else body
    return await create_watch(case_id, effective)

@app.post("/api/v1/mobile/wallet/trace", response_model=TraceResult)
async def mobile_trace_wallet(body: MobileTraceRequest):
    request=TraceRequest(address=body.address,chain=body.chain,direction=body.direction,max_hops=body.max_hops,max_nodes=body.max_nodes,max_edges=body.max_edges,max_transactions=body.max_transactions)
    return await trace_case(body.case_id, request)

@app.get("/api/v1/cases/{case_id}/workflow")
async def case_workflow(case_id: str):
    await get_case(case_id)
    try: return await repo.workflow_events(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/changes", response_model=list[InvestigationChangeSet])
async def case_changes(case_id: str):
    await get_case(case_id)
    try: return await repo.change_sets(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/audit-events", response_model=list[AuditEvent])
async def case_audit_events(case_id: str):
    await get_case(case_id)
    try: return await repo.audit_events(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/related", response_model=list[CaseLink])
async def related_cases(case_id: str):
    await get_case(case_id)
    try: return await repo.related_cases(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/alerts", response_model=list[Alert])
async def realtime_alerts(case_id: str):
    await get_case(case_id)
    try: return await repo.alerts(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/alerts", response_model=list[Alert])
async def all_alerts():
    try: return await repo.all_alerts()
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/alerts/{alert_id}/review", response_model=Alert)
async def review_alert(case_id: str, alert_id: str, body: AlertReviewRequest):
    try: return await alert_service.review(case_id, alert_id, body)
    except ValueError as exc: raise HTTPException(409 if "transition" in str(exc) else 404, str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/alerts/{alert_id}/reviews", response_model=list[AlertReview])
async def alert_review_history(case_id: str, alert_id: str):
    await get_case(case_id)
    try:
        if not await repo.get_alert(case_id, alert_id): raise HTTPException(404, "Alert not found")
        return await alert_service.history(case_id, alert_id)
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/cross-chain/observations")
async def cross_chain_observation(case_id: str, body: CrossChainObservationCreate):
    try:
        result=await cross_chain_service.ingest_observation(case_id,body)
        logging.getLogger("crypto_fraud_intelligence").info("cross_chain_observation_ingested",extra={"case_id":case_id,"chain":body.transfer.chain,"tx_hash":body.transfer.tx_hash})
        return {"status":"OBSERVED" if body.mode != DataMode.SIMULATED else "SIMULATED","persisted":bool(result)}
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.post("/api/v1/cases/{case_id}/cross-chain/analyze",response_model=CrossChainTrace)
async def analyze_cross_chain(case_id: str, body: CrossChainAnalyzeRequest = CrossChainAnalyzeRequest()):
    try:
        result=await cross_chain_service.analyze(case_id,body)
        await repo.append_timeline(TimelineEvent(event_id=str(uuid4()),case_id=case_id,timestamp=datetime.now(timezone.utc),event_type="CROSS_CHAIN_ACTIVITY",summary=f"Cross-chain analysis completed across {len(result.chains_visited)} supported chain(s); relationships remain confidence-scored inferences.",source="CrossChainEngine",evidence_ids=list(dict.fromkeys(e for link in result.cross_chain_links for e in link.evidence_ids)),metadata={"trace_id":result.trace_id,"status":result.status,"cross_chain_hops":result.cross_chain_hops}))
        try:
            assessment=await risk_service.assess(case_id,RiskAssessRequest())
            await repo.append_timeline(TimelineEvent(event_id=str(uuid4()),case_id=case_id,timestamp=assessment.calculated_at,event_type="RISK_REASSESSED",summary=f"Risk posture reassessed with persisted cross-chain observations: {assessment.band} ({assessment.score:.1f}/100).",source="RuleBasedRiskEngine",evidence_ids=assessment.evidence_ids,metadata={"assessment_id":assessment.assessment_id,"delta":assessment.delta.delta if assessment.delta else 0}))
        except ValueError:
            pass
        return result
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/cross-chain",response_model=CrossChainSummary)
async def cross_chain_summary(case_id: str):
    await get_case(case_id)
    try: return await cross_chain_service.summary(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/cross-chain/links",response_model=list[CrossChainLink])
async def cross_chain_links(case_id: str):
    await get_case(case_id)
    try: return await cross_chain_service.links(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/cross-chain/patterns",response_model=list[CrossChainPatternObservation])
async def cross_chain_patterns(case_id: str):
    await get_case(case_id)
    try: return await cross_chain_service.patterns(case_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/cross-chain/paths")
async def cross_chain_paths(case_id: str):
    await get_case(case_id)
    try:
        links=await cross_chain_service.links(case_id)
        return {"links":links,"paths":[],"note":"Persisted path reconstruction will be expanded from cross_chain_trace_edges; links retain source/destination evidence and confidence."}
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/cases/{case_id}/cross-chain/timeline",response_model=list[TimelineEvent])
async def cross_chain_timeline(case_id: str):
    await get_case(case_id)
    try: return [item for item in await repo.timeline(case_id) if item.event_type.startswith("CROSS_CHAIN") or item.event_type.startswith("BRIDGE")]
    except DatabaseError as exc: return database_failure(exc)
