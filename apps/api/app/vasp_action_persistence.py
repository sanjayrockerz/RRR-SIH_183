import json
from uuid import UUID
import asyncpg
from .domain import VaspActionPackage

class VaspActionPersistenceMixin:
    async def persist_vasp_action_package(self, package):
        async with self._require_pool().acquire() as conn:
            await conn.execute("INSERT INTO vasp_action_packages(package_id,case_id,report_id,package_version,payload,integrity_hash,created_at,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8)", UUID(package.package_id), UUID(package.case_id), UUID(package.report_id), package.report_version, json.dumps(package.model_dump(mode="json")), package.integrity_hash, package.generated_at, None)
        return package

    @staticmethod
    def _package(row):
        return VaspActionPackage.model_validate(row["payload"])

    async def list_vasp_action_packages(self, case_id):
        async with self._require_pool().acquire() as conn:
            rows = await conn.fetch("SELECT payload FROM vasp_action_packages WHERE case_id=$1 ORDER BY created_at DESC", UUID(case_id))
        return [self._package(row) for row in rows]

    async def get_latest_vasp_action_package(self, case_id):
        async with self._require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT payload FROM vasp_action_packages WHERE case_id=$1 ORDER BY created_at DESC LIMIT 1", UUID(case_id))
        return self._package(row) if row else None
