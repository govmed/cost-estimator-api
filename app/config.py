from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://sow_calc:devpassword@localhost:5432/sow_calc"
    secret_key: str = "dev-secret-change-in-production"
    auth_mode: str = "standalone"  # standalone | oidc
    environment: str = "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
