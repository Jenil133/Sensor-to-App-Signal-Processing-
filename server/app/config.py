from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://baseline:baseline@localhost:5432/baseline"
    jwt_secret: str = "dev-only-change-me"
    jwt_expires_min: int = 60
    payload_enc_key: str  # REQUIRED: Fernet key; app must fail fast if missing
    cors_origins: str = "http://localhost:5173"


settings = Settings()
