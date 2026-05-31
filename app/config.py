from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-secret-change-in-production"
_DEV_DB_MARKER = "devpassword"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = f"postgresql+psycopg2://sow_calc:{_DEV_DB_MARKER}@localhost:5432/sow_calc"
    secret_key: str = _DEV_SECRET
    auth_mode: str = "standalone"  # standalone | oidc
    authentik_issuer: str = ""
    environment: str = "development"

    # Comma-separated list of allowed CORS origins.
    # Default covers the SPA dev server. Override in production.
    # Example: https://cost-estimator.azurestaticapps.net,https://cost.example.com
    allowed_origins: str = "http://localhost:5173"

    # Rate limiting (requests per window, per IP)
    rate_limit_auth: str = "10/minute"   # login / register
    rate_limit_default: str = "60/minute"  # all other endpoints

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def use_oidc(self) -> bool:
        return self.auth_mode == "oidc"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    def validate_production_secrets(self) -> None:
        """Raise at startup if obviously-insecure defaults are used in production."""
        if not self.is_production:
            return
        errors: list[str] = []
        if self.secret_key == _DEV_SECRET:
            errors.append("SECRET_KEY is the dev default — set a strong random value.")
        if _DEV_DB_MARKER in self.database_url:
            errors.append("DATABASE_URL contains the dev password — set a real credential.")
        if self.use_oidc and not self.authentik_issuer:
            errors.append("AUTH_MODE=oidc but AUTHENTIK_ISSUER is not set.")
        if errors:
            raise RuntimeError(
                "Production startup blocked — insecure configuration:\n"
                + "\n".join(f"  • {e}" for e in errors)
            )


settings = Settings()
