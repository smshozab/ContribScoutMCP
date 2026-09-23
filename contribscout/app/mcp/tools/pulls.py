from ...config import get_settings
from .common import error_result, github_for_url


async def list_pull_requests(repo_url: str, state: str = "open", max_results: int = 30) -> dict:
    """List pull request metadata for a repository."""
    if state not in {"open", "closed", "all"} or not 1 <= max_results <= 100:
        return {"error": {"type": "invalid_input", "message": "state must be open, closed, or all; max_results must be 1-100."}}
    try:
        async with github_for_url(repo_url, "list_pull_requests") as (client, owner, repo):
            items = await client.pull_requests(owner, repo, state, min(max_results, get_settings().max_prs))
            return {"pull_requests": [x.model_dump() for x in items], "count": len(items)}
    except Exception as exc:
        return error_result(exc)
