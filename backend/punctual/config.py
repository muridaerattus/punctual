from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PUNCTUAL_")

    api_key: str = Field(default="", repr=False)
    db: str = "punctual.db"
    static: Path = Path(__file__).resolve().parents[2] / "frontend/dist"
    allowed_hosts: str = ""
    allowed_origins: str = ""

    @property
    def host_list(self) -> list[str]:
        return self.split_list(self.allowed_hosts)

    @property
    def origin_list(self) -> list[str]:
        return self.split_list(self.allowed_origins)

    @staticmethod
    def split_list(value: str) -> list[str]:
        return [part.strip() for part in value.split(",") if part.strip()]
