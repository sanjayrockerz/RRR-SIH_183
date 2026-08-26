from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    alchemy_api_key: str | None = None
    alchemy_network: str = "eth-mainnet"
    api_origin: str = "http://localhost:8000"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/crypto_fraud_intelligence"
    database_min_pool_size: int = 1
    database_max_pool_size: int = 5
    alchemy_page_size: int = 100
    alchemy_max_pages: int = 10
    alchemy_max_transactions: int = 500
    trace_default_hops: int = 2
    trace_default_max_nodes: int = 100
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
