from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os


class Settings(BaseSettings):
    # ── Mail ────────────────────────────────────────────
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    email_from: str = Field(default="")

    smtp_use_tls: bool = Field(default=True)
    smtp_use_ssl: bool = Field(default=False)
    smtp_timeout: int = Field(default=30)

    # ── Email Generation API ────────────────────────────
    email_api_key: str = Field(default="")
    email_api_url: str = Field(default="https://api.openai.com/v1/chat/completions")

    # ── Database ───────────────────────────────────────
    sqlite_path: Path = Field(default=Path(__file__).parent / "database.db")

    # ── Validators ─────────────────────────────────────
    @field_validator("smtp_port")
    @classmethod
    def validate_smtp_port(cls, v):
        if v not in [25, 465, 587]:
            raise ValueError("SMTP port must be 25, 465, or 587")
        return v

    # ── Utility Methods ────────────────────────────────
    @property
    def smtp_configured(self) -> bool:
        return all([
            self.smtp_host,
            self.smtp_username,
            self.smtp_password,
            self.email_from
        ])

    @property
    def email_api_configured(self) -> bool:
        return bool(self.email_api_key and self.email_api_url)

    def validate_smtp_settings(self) -> List[str]:
        errors = []
        if not self.smtp_host:
            errors.append("SMTP host is required")
        if not self.smtp_username:
            errors.append("SMTP username is required")
        if not self.smtp_password:
            errors.append("SMTP password is required")
        if not self.email_from:
            errors.append("Email from address is required")
        return errors

    def validate_email_api_settings(self) -> List[str]:
        errors = []
        if not self.email_api_key:
            errors.append("Email API key is required")
        if not self.email_api_url:
            errors.append("Email API URL is required")
        return errors

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    print("DEBUG ENV:", os.environ.get("EMAIL_API_KEY"))
    return Settings()
