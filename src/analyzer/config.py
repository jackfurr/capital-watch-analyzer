"""Configuration settings for the analyzer."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Configuration
    scraper_api_url: str = Field(default="http://localhost:8000", alias="SCRAPER_API_URL")
    scraper_api_key: str = Field(default="", alias="SCRAPER_API_KEY")

    # Report Configuration
    reports_dir: str = Field(default="./reports", alias="REPORTS_DIR")
    weekly_report_day: int = Field(default=3, alias="WEEKLY_REPORT_DAY")  # 3 = Wednesday

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")

    # Email Configuration (optional)
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_pass: str | None = Field(default=None, alias="SMTP_PASS")
    email_from: str | None = Field(default=None, alias="EMAIL_FROM")
    email_to: str | None = Field(default=None, alias="EMAIL_TO")

    # Discord Configuration (optional)
    discord_webhook_url: str | None = Field(default=None, alias="DISCORD_WEBHOOK_URL")

    @property
    def api_headers(self) -> dict[str, str]:
        """Return headers for API requests including auth."""
        headers = {"Content-Type": "application/json"}
        if self.scraper_api_key:
            headers["X-API-Key"] = self.scraper_api_key
        return headers


# Global settings instance
settings = Settings()
