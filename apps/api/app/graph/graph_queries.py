from .neo4j_repository import Neo4jGraphRepository


class GraphQueryService:
    """Explicit query boundary for relationship intelligence operations."""

    def __init__(self, repository: Neo4jGraphRepository):
        self.repository = repository

    async def neighbors(self, case_id: str, address: str, depth: int = 1):
        return await self.repository.neighbors(case_id, address, depth)

    async def shortest_path(self, case_id: str, source: str, destination: str):
        return await self.repository.shortest_path(case_id, source, destination)
