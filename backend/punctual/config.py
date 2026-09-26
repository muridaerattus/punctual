from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PUNCTUAL_")

    api_key: str = Field(default="", repr=False)
    db: str = "punctual.db"
    static: Path = Path(__file__).resolve().parents[2] / "frontend/dist"
    allowed_hosts: str = ""
    allowed_origins: str = ""
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = Field(default="", repr=False)
    public_url: str = ""
    oidc_group: str = ""
    session_seconds: int = Field(default=900, ge=60, le=3600)
    mcp_issuer: str = ""
    mcp_jwks_url: str = ""
    mcp_resource: str = ""
    mcp_group: str = ""
    mcp_scopes: str = ""
    mcp_token_profile: Literal["rfc9068", "authentik"] = "rfc9068"

    @model_validator(mode="after")
    def validate_mcp_oauth(self):
        values = (
            self.mcp_issuer,
            self.mcp_jwks_url,
            self.mcp_resource,
            self.mcp_group,
            self.mcp_scopes,
        )
        if any(values):
            if not all(value.strip() for value in values):
                raise ValueError("All MCP OAuth settings must be configured")
            for value in values[:3]:
                url = urlsplit(value)
                if (
                    url.scheme != "https"
                    or not url.netloc
                    or url.username
                    or url.password
                    or url.query
                    or url.fragment
                ):
                    raise ValueError("MCP OAuth URLs must be absolute HTTPS URLs")
            if urlsplit(self.mcp_resource).path not in ("/mcp", "/mcp/"):
                raise ValueError("MCP resource must identify /mcp or /mcp/")
            if any(
                not 33 <= ord(c) <= 126 or c in '\\"'
                for scope in self.mcp_scopes.split()
                for c in scope
            ):
                raise ValueError("Invalid MCP OAuth scope")
        return self

    @model_validator(mode="after")
    def validate_oidc(self):
        values = (
            self.oidc_issuer,
            self.oidc_client_id,
            self.oidc_client_secret,
            self.public_url,
        )
        if any(values):
            if not all(values) or not self.oidc_group.strip():
                raise ValueError(
                    "All OIDC settings and a required group must be configured"
                )
            for value in (self.oidc_issuer, self.public_url):
                url = urlsplit(value)
                if (
                    url.scheme != "https"
                    or not url.netloc
                    or url.username
                    or url.password
                    or url.query
                    or url.fragment
                ):
                    raise ValueError(
                        "OIDC issuer and public URL must be absolute HTTPS URLs"
                    )
            if urlsplit(self.public_url).path not in ("", "/"):
                raise ValueError("Public URL must be an origin without a path")
            self.public_url = self.public_url.rstrip("/")
        return self

    @property
    def host_list(self) -> list[str]:
        return self.split_list(self.allowed_hosts)

    @property
    def origin_list(self) -> list[str]:
        return self.split_list(self.allowed_origins)

    @staticmethod
    def split_list(value: str) -> list[str]:
        return [part.strip() for part in value.split(",") if part.strip()]
