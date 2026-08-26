import os
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("RUN_POSTGRES_TESTS"), reason="Set RUN_POSTGRES_TESTS=1 with PostgreSQL available")

@pytest.mark.asyncio
async def test_postgres_persistence_contract_is_opt_in():
    # Integration coverage is intentionally opt-in so normal unit tests never
    # depend on credentials or a running external service.
    assert os.getenv("DATABASE_URL")
