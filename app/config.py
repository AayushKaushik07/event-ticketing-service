from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, read from environment variables.

    Nothing environment-dependent is hardcoded anywhere else in the codebase.
    That is what lets the same container image run locally, in CI and in the
    cloud with only the environment changing.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    app_env: str = "local"


settings = Settings()
