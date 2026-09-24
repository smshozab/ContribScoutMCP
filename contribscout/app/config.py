from functools import lru_cache
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
