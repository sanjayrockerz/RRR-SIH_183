import logging

from .attribution import AttributionEngine, NearestEntityResolver
from .domain import PatternAnalyzeRequest, PatternObservation, PatternSummary, TraceResult
from .pattern_engine import PatternEngine

logger = logging.getLogger("crypto_fraud_intelligence")


class PatternService:
    """Application boundary for explicit, bounded pattern analysis."""
    def __init__(self, repository, engine: PatternEngine | None = None):
        self.repository = repository
        self.engine = engine or PatternEngine()

    async def analyze(self, trace: TraceResult, request: PatternAnalyzeRequest, attributions=()) -> list[PatternObservation]:
        engine = PatternEngine(request.config)
        observations = engine.analyze(trace, list(attributions))
        persisted = await self.repository.persist_patterns(observations)
        logger.info("patterns_analyzed", extra={"case_id": trace.case_id, "trace_id": trace.trace_id, "pattern_count": len(persisted)})
        return persisted

    async def list(self, case_id: str, trace_id: str | None = None):
        return await self.repository.list_patterns(case_id, trace_id)

    async def list_by_trace(self, trace_id: str):
        return await self.repository.list_patterns_by_trace(trace_id)

    async def get(self, case_id: str, pattern_id: str):
        return await self.repository.get_pattern(case_id, pattern_id)

    async def summary(self, case_id: str, trace_id: str | None = None) -> PatternSummary:
        return await self.repository.pattern_summary(case_id, trace_id)
