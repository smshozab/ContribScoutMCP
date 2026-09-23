import logging
from contextlib import asynccontextmanager

from ...github.client import GitHubClient
from ...github.exceptions import GitHubError, InvalidRepositoryURL
from ...github.parser import parse_repository_url

logger = logging.getLogger("contribscout.tools")


@asynccontextmanager
async def github_for_url(repo_url: str, request_type: str = "github_read"):
    owner, repo = parse_repository_url(repo_url)
    client = GitHubClient()
    logger.info("request_type=%s owner=%s repo=%s", request_type, owner, repo)
    try:
        yield client, owner, repo
    finally:
        await client.close()


def error_result(exc: Exception) -> dict:
    if isinstance(exc, InvalidRepositoryURL):
        return {"error": {"type": "invalid_repository_url", "message": str(exc)}}
    if isinstance(exc, GitHubError):
        return {"error": {"type": exc.kind, "message": str(exc)}}
    logger.exception("Unexpected tool failure", exc_info=exc)
    return {"error": {"type": "internal_error", "message": "The request could not be completed."}}
