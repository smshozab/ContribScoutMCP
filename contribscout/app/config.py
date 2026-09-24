from functools import lru_cache
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic import AnyHttpUrl, model_validator
from typing_extensions import Self

load_dotenv()


class Settings(BaseModel):
    github_token: str | None = Field(default_factory=lambda: os.getenv("GITHUB_TOKEN") or None)
    github_api_url: str = Field(default_factory=lambda: os.getenv("GITHUB_API_URL", "https://api.github.com"))
    request_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")))
    max_file_size: int = Field(default_factory=lambda: int(os.getenv("MAX_FILE_SIZE", "200000")))
    max_files_to_scan: int = Field(default_factory=lambda: int(os.getenv("MAX_FILES_TO_SCAN", "60")))
    max_issues: int = Field(default_factory=lambda: int(os.getenv("MAX_ISSUES", "100")))
    max_prs: int = Field(default_factory=lambda: int(os.getenv("MAX_PRS", "100")))
    max_results: int = Field(default_factory=lambda: int(os.getenv("MAX_RESULTS", "20")))
    mcp_rate_limit_per_minute: int = Field(
        default_factory=lambda: int(os.getenv("MCP_RATE_LIMIT_PER_MINUTE", "30")), ge=1, le=1000
    )
    mcp_oauth_issuer_url: AnyHttpUrl | None = Field(default_factory=lambda: os.getenv("MCP_OAUTH_ISSUER_URL") or None)
    mcp_oauth_resource_url: AnyHttpUrl | None = Field(default_factory=lambda: os.getenv("MCP_OAUTH_RESOURCE_URL") or None)
    mcp_oauth_audience: str | None = Field(default_factory=lambda: os.getenv("MCP_OAUTH_AUDIENCE") or None)
    mcp_oauth_required_scopes: list[str] = Field(
        default_factory=lambda: os.getenv("MCP_OAUTH_REQUIRED_SCOPES", "contribscout:read").split()
    )

    @model_validator(mode="after")
    def validate_oauth_settings(self) -> Self:
        values = (self.mcp_oauth_issuer_url, self.mcp_oauth_resource_url, self.mcp_oauth_audience)
        if any(values) and not all(values):
            raise ValueError(
                "Configure MCP_OAUTH_ISSUER_URL, MCP_OAUTH_RESOURCE_URL, and MCP_OAUTH_AUDIENCE together"
            )
        if not self.mcp_oauth_required_scopes or any(not scope.strip() for scope in self.mcp_oauth_required_scopes):
            raise ValueError("MCP_OAUTH_REQUIRED_SCOPES must contain at least one scope")
        if self.mcp_oauth_audience and not self.mcp_oauth_audience.strip():
            raise ValueError("MCP_OAUTH_AUDIENCE cannot be blank")
        for field_name in ("mcp_oauth_issuer_url", "mcp_oauth_resource_url"):
            url = getattr(self, field_name)
            if url:
                parsed = AnyHttpUrl(str(url))
                if parsed.scheme != "https" and parsed.host not in {"localhost", "127.0.0.1"}:
                    raise ValueError("OAuth issuer and resource URLs must use HTTPS")
                object.__setattr__(self, field_name, parsed)
        if self.mcp_oauth_resource_url and self.mcp_oauth_audience:
            if self.mcp_oauth_audience != str(self.mcp_oauth_resource_url):
                raise ValueError("For Auth0, MCP_OAUTH_AUDIENCE must exactly match the normalized MCP_OAUTH_RESOURCE_URL")
        return self

    @property
    def oauth_enabled(self) -> bool:
        return bool(self.mcp_oauth_issuer_url and self.mcp_oauth_resource_url and self.mcp_oauth_audience)


@lru_cache
def get_settings() -> Settings:
    return Settings()
