from __future__ import annotations

from typing import Any
from ..config import settings
from ..domain import CapabilityStatus

try:
    from neo4j import AsyncGraphDatabase
except ImportError:  # pragma: no cover - exercised only in minimal installations
    AsyncGraphDatabase = None


class Neo4jClient:
    def __init__(self):
        self.driver = None
        self.status = CapabilityStatus.NOT_CONFIGURED
        self.detail = "NEO4J_URI and NEO4J_PASSWORD are required"

    @property
    def configured(self) -> bool:
        return bool(settings.neo4j_uri and settings.neo4j_password)

    async def connect(self) -> None:
        if not self.configured:
            return
        if AsyncGraphDatabase is None:
            self.status = CapabilityStatus.UNSUPPORTED
            self.detail = "neo4j driver is not installed"
            return
        try:
            self.driver = AsyncGraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password), connection_timeout=settings.neo4j_connect_timeout)
            await self.driver.verify_connectivity()
            self.status = CapabilityStatus.SUPPORTED
            self.detail = "Neo4j projection is connected"
        except Exception as exc:  # driver exposes several transport-specific errors
            self.status = CapabilityStatus.UNAVAILABLE
            self.detail = f"Neo4j unavailable: {type(exc).__name__}"
            if self.driver:
                await self.driver.close()
                self.driver = None

    async def close(self) -> None:
        if self.driver:
            await self.driver.close()
            self.driver = None

    async def run(self, query: str, **params: Any) -> list[dict]:
        if not self.driver:
            raise RuntimeError(self.detail)
        async with self.driver.session(database=settings.neo4j_database) as session:
            result = await session.run(query, params)
            return [record.data() async for record in result]
