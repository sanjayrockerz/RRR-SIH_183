from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # ENVIRONMENT is the deployment contract; APP_ENV remains a compatibility alias.
    environment: str | None = None
    app_env: str = "development"
    demo_mode: bool = False
    rrr_demo_user: str = "RRR@SIH"
    rrr_demo_password: str = "SIH@2026"
    alchemy_api_key: str | None = None
    alchemy_webhook_signing_key: str | None = None
    alchemy_webhook_id: str | None = None
    alchemy_auth_token: str | None = None
    alchemy_network: str = "eth-mainnet"
    trongrid_api_key: str | None = None
    trongrid_base_url: str = "https://api.trongrid.io"
    chainabuse_api_key: str | None = None
    chainabuse_base_url: str = "https://api.chainabuse.com/v0"
    chainabuse_source_version: str = "chainabuse-public-v1.2"
    threat_intel_timeout_seconds: float = 15.0
    recommendation_ruleset_version: str = "phase7-recommendations-v1"
    recommendation_vasp_max_hops: int = 6
    recommendation_risk_delta_threshold: float = 10.0
    bridge_registry_file: str = "data/bridges/bridge_registry.json"
    api_origin: str = "http://localhost:8000"
    frontend_origin: str | None = None
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
    jwt_secret: str | None = None
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
    realtime_material_risk_delta_threshold: float = 10.0
    redis_url: str | None = None
    rrr_ml_model_path: str = "models/rrr_ethereum_wallet_xgb_v2.joblib"
    rrr_ml_metadata_path: str = "models/rrr_ethereum_wallet_xgb_v2_metadata.json"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def effective_environment(self) -> str:
        return (self.environment or self.app_env).strip().lower()

    @property
    def is_production(self) -> bool:
        return self.effective_environment == "production"

    def validate_production(self) -> list[str]:
        """Return missing core production configuration without exposing values."""
        if not self.is_production:
            return []
        missing = []
        for name, value in (
            ("DATABASE_URL", self.database_url),
            ("FRONTEND_ORIGIN", self.frontend_origin),
            ("RRR_ML_MODEL_PATH", self.rrr_ml_model_path),
            ("RRR_ML_METADATA_PATH", self.rrr_ml_metadata_path),
        ):
            if not value or "localhost" in value.lower() and name == "DATABASE_URL":
                missing.append(name)
        if not (self.jwt_secret or self.auth_jwt_public_key):
            missing.append("JWT_SECRET or AUTH_JWT_PUBLIC_KEY")
        if self.blockchain_data_mode.upper() == "DEVELOPMENT_FIXTURE":
            missing.append("BLOCKCHAIN_DATA_MODE must not be DEVELOPMENT_FIXTURE")
        return missing

    @property
    def cors_origins(self) -> list[str]:
        """Build the full list of allowed CORS origins."""
        base = [self.api_origin]
        if not self.is_production:
            base.extend([
                "http://localhost:5173", "http://127.0.0.1:5173",
                "http://localhost:5174", "http://127.0.0.1:5174",
                "http://localhost:5175", "http://127.0.0.1:5175",
                "http://localhost:4173", "http://127.0.0.1:4173",
            ])
        if self.frontend_origin:
            base.append(self.frontend_origin.rstrip("/"))
        if self.cors_extra_origins:
            base.extend(o.strip() for o in self.cors_extra_origins.split() if o.strip())
        return list(dict.fromkeys(base))

settings = Settings()
