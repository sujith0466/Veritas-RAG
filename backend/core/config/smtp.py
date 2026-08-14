"""SMTP-level configuration settings."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class SmtpSettings(BaseSettings):
    """SMTP configuration for outbound email delivery."""

    host: str = Field(default="", alias="SMTP_HOST")
    port: int = Field(default=587, alias="SMTP_PORT")
    user: str = Field(default="", alias="SMTP_USER")
    password: SecretStr = Field(default=SecretStr(""), alias="SMTP_PASSWORD")
    from_email: str = Field(default="noreply@raguard.ai", alias="SMTP_FROM_EMAIL")
    tls_mode: str = Field(default="starttls", alias="SMTP_TLS_MODE")
    timeout: float = Field(default=10.0, alias="SMTP_TIMEOUT")

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }

    @property
    def is_configured(self) -> bool:
        """Returns True if the required SMTP settings are present."""
        return bool(self.host and self.port)
