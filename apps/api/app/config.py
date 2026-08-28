from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    alchemy_api_key: str | None = None
    alchemy_webhook_signing_key: str | None = None
    alchemy_webhook_id: str | None = None
    alchemy_auth_token: str | None = None
    alchemy_network: str = "eth-mainnet"
    trongrid_api_key: str | None = None
    trongrid_base_url: str = "https://api.trongrid.io"
    bridge_registry_file: str = "data/bridges/bridge_registry.json"
    api_origin: str = "http://localhost:8000"
    # Space-separated list of additional allowed CORS origins (e.g. Vercel preview URLs).
    # Example: CORS_EXTRA_ORIGINS="https://my-app.vercel.app https://my-app-git-main.vercel.app"
    cors_extra_origins: str = ""
    database_url: str = "postgresql://postgres:postgres@localhost:5432/crypto_fraud_intelligence"
    database_min_pool_size: int = 1
    database_max_pool_size: int = 5
    database_auto_migrate: bool = True
    blockchain_data_mode: str = "LIVE"
    neo4j_uri: str | None = None
    neo4j_username: str = "neo4j"
    neo4j_password: str | None = None
    neo4j_database: str = "neo4j"
    neo4j_connect_timeout: float = 5.0
    provider_timeout_seconds: float = 30.0
    provider_max_retries: int = 2
    auth_required: bool = False
    auth_jwt_public_key: str | None = None
    auth_jwt_issuer: str | None = None
    auth_jwt_audience: str | None = None
    alchemy_base_url: str | None = None
    alchemy_page_size: int = 100
    alchemy_max_pages: int = 10
    alchemy_max_transactions: int = 500
    alchemy_timeout_seconds: float = 30.0
    trace_default_hops: int = 2
    trace_default_max_nodes: int = 100
    realtime_required_confirmations: int = 3
    realtime_max_payload_bytes: int = 1000000
    realtime_event_replay_seconds: int = 86400
    realtime_max_processing_attempts: int = 3
    realtime_retry_delay_seconds: int = 30
    redis_url: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        """Build the full list of allowed CORS origins."""
        base = [
            self.api_origin,
            # Vite dev server — includes fallback ports when 5173 is taken
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
        if self.cors_extra_origins:
            base.extend(o.strip() for o in self.cors_extra_origins.split() if o.strip())
        return list(dict.fromkeys(base))

settings = Settings()
