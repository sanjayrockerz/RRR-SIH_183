from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .domain import *
from .persistence import PostgresCaseRepository, DatabaseError
from .provider import AlchemyEthereumProvider, ProviderError
from .services import TraceService
from .attribution import AttributionEngine, NearestEntityResolver
from .pattern_service import PatternService
from .risk_service import RiskService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
provider=AlchemyEthereumProvider(); repo=PostgresCaseRepository(); tracer=TraceService(provider); pattern_service=PatternService(repo); risk_service=RiskService(repo)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await repo.connect()
    try: yield
    finally: await repo.close()

app=FastAPI(title="Crypto Fraud Intelligence API",version="0.1.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[settings.api_origin,"http://localhost:5173"],allow_methods=["*"],allow_headers=["*"])

@app.get("/health")
async def health():
    return {"status":"ok","service":"crypto-fraud-intelligence-api","persistence":"postgresql"}

@app.get("/api/v1/provider/capabilities",response_model=list[ProviderCapability])
async def capabilities(): return provider.capabilities()

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

def database_failure(exc: DatabaseError):
    logging.getLogger("crypto_fraud_intelligence").error("database_error",extra={"error_type":type(exc).__name__})
    raise HTTPException(503,"Persistent storage is unavailable") from exc

@app.post("/api/v1/cases",response_model=InvestigationCase)
async def create_case(body: CaseCreate):
    try:
        result=await repo.create(body); logging.getLogger("crypto_fraud_intelligence").info("case_created",extra={"case_id":result.case_id}); return result
    except DatabaseError as exc: return database_failure(exc)

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
        logging.getLogger("crypto_fraud_intelligence").info("wallet_added",extra={"case_id":case_id,"chain":body.chain}); return result
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
async def read_case(case_id: str): return await get_case(case_id)

@app.post("/api/v1/cases/{case_id}/traces",response_model=TraceResult)
async def trace_case(case_id: str, body: TraceRequest):
    await get_case(case_id)
    try:
        logging.getLogger("crypto_fraud_intelligence").info("trace_started",extra={"case_id":case_id,"address":body.address.lower()})
        result=await tracer.trace(case_id,body); await repo.persist_trace(result); return result
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

@app.get("/api/v1/cases/{case_id}/traces/{trace_id}",response_model=TraceResult)
async def read_trace(case_id: str, trace_id: str):
    await get_case(case_id)
    try:
        result=await repo.get_trace(case_id,trace_id)
        if not result: raise HTTPException(404,"Trace not found")
        return result
    except DatabaseError as exc: return database_failure(exc)

async def _trace_for_patterns(case_id: str, trace_id: str | None):
    case=await get_case(case_id)
    if trace_id:
        result=await repo.get_trace(case_id,trace_id)
        if not result: raise HTTPException(404,"Trace not found")
        return result
    if not case.latest_trace: raise HTTPException(404,"No persisted trace for case")
    return case.latest_trace

async def _case_attributions(trace: TraceResult):
    entities,sources,records=await repo.attribution_catalog()
    return NearestEntityResolver(AttributionEngine(entities,sources,records)).resolve(trace)

@app.post("/api/v1/cases/{case_id}/patterns/analyze",response_model=list[PatternObservation])
async def analyze_patterns(case_id: str, body: PatternAnalyzeRequest = PatternAnalyzeRequest()):
    try:
        trace=await _trace_for_patterns(case_id,body.trace_id)
        attributions=await _case_attributions(trace)
        return await pattern_service.analyze(trace,body,attributions)
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
    try: return await risk_service.assess(case_id,body)
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
    try: return await risk_service.subject(wallet_id)
    except DatabaseError as exc: return database_failure(exc)

@app.get("/api/v1/traces/{trace_id}/risk",response_model=list[RiskAssessment])
async def trace_risk(trace_id: str):
    try: return await risk_service.trace(trace_id)
    except DatabaseError as exc: return database_failure(exc)
