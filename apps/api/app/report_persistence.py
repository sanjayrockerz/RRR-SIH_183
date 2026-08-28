import json
from uuid import UUID
import asyncpg

from .domain import InvestigationReport, ReportType


class ReportPersistenceMixin:
    async def persist_report(self, report: InvestigationReport) -> InvestigationReport:
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                await conn.execute("INSERT INTO investigation_reports(report_id,case_id,report_type,trace_id,title,content,evidence_ids,pattern_ids,assessment_id,content_hash,created_at,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)", UUID(report.report_id), UUID(report.case_id), report.report_type.value, UUID(report.trace_id) if report.trace_id else None, report.title, report.content, json.dumps(report.evidence_ids), json.dumps(report.pattern_ids), UUID(report.assessment_id) if report.assessment_id else None, report.content_hash, report.created_at, report.created_by)
            return report
        except asyncpg.PostgresError as exc:
            if isinstance(exc, asyncpg.PostgresError):
                from .persistence import DatabaseError
                raise DatabaseError("Report could not be persisted") from exc
            raise

    @staticmethod
    def _report(row) -> InvestigationReport:
        def array(value):
            return json.loads(value) if isinstance(value, str) else (value or [])
        return InvestigationReport(report_id=str(row["report_id"]), case_id=str(row["case_id"]), report_type=ReportType(row["report_type"]), trace_id=str(row["trace_id"]) if row["trace_id"] else None, title=row["title"], content=row["content"], evidence_ids=array(row["evidence_ids"]), pattern_ids=array(row["pattern_ids"]), assessment_id=str(row["assessment_id"]) if row["assessment_id"] else None, content_hash=row["content_hash"], created_at=row["created_at"], created_by=row["created_by"])

    async def list_reports(self, case_id: str) -> list[InvestigationReport]:
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM investigation_reports WHERE case_id=$1 ORDER BY created_at DESC", UUID(case_id))
            return [self._report(row) for row in rows]
        except (asyncpg.PostgresError, ValueError) as exc:
            if isinstance(exc, asyncpg.PostgresError) or isinstance(exc, ValueError):
                from .persistence import DatabaseError
                raise DatabaseError("Reports could not be retrieved") from exc
            raise

    async def get_report(self, case_id: str, report_id: str) -> InvestigationReport | None:
        pool = self._require_pool()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM investigation_reports WHERE case_id=$1 AND report_id=$2", UUID(case_id), UUID(report_id))
            return self._report(row) if row else None
        except (asyncpg.PostgresError, ValueError) as exc:
            if isinstance(exc, asyncpg.PostgresError) or isinstance(exc, ValueError):
                from .persistence import DatabaseError
                raise DatabaseError("Report could not be retrieved") from exc
            raise
