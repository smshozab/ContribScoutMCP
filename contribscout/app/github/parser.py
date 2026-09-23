import re
from urllib.parse import urlparse

from .exceptions import InvalidRepositoryURL

_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def parse_repository_url(value: str) -> tuple[str, str]:
    """Return owner/repo for supported HTTPS and SCP-style GitHub URLs."""
    if not isinstance(value, str) or not value.strip():
        raise InvalidRepositoryURL("Provide a GitHub repository URL.")
    raw = value.strip()
    if raw.startswith("git@"):
        match = re.fullmatch(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?", raw, re.IGNORECASE)
        if not match:
            raise InvalidRepositoryURL("Expected git@github.com:owner/repo.git.")
        owner, repo = match.groups()
    else:
        try:
            parsed = urlparse(raw)
            if parsed.scheme.lower() not in {"http", "https"} or (parsed.hostname or "").lower() != "github.com":
                raise InvalidRepositoryURL("Only public github.com repository URLs are supported.")
            if parsed.username or parsed.password or parsed.port:
                raise InvalidRepositoryURL("Credentials and custom ports are not allowed in repository URLs.")
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) != 2:
                raise InvalidRepositoryURL("Expected a repository URL like https://github.com/owner/repo.")
            owner, repo = parts
        except ValueError as exc:
            if isinstance(exc, InvalidRepositoryURL):
                raise
            raise InvalidRepositoryURL("Invalid GitHub repository URL.") from None
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not _NAME.fullmatch(owner) or not _NAME.fullmatch(repo) or owner in {".", ".."} or repo in {".", ".."}:
        raise InvalidRepositoryURL("Repository URL contains an invalid owner or repository name.")
    return owner, repo
