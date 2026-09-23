from .common import error_result, github_for_url


async def get_repository(repo_url: str) -> dict:
    """Fetch normalized metadata for a public GitHub repository URL."""
    try:
        async with github_for_url(repo_url, "get_repository") as (client, owner, repo):
            return (await client.repository(owner, repo)).model_dump()
    except Exception as exc:
        return error_result(exc)


async def get_repository_tree(repo_url: str) -> dict:
    """List paths and blob metadata from the repository's default branch."""
    try:
        async with github_for_url(repo_url, "get_repository_tree") as (client, owner, repo):
            entries, truncated = await client.tree(owner, repo)
            return {"entries": [x.model_dump() for x in entries], "count": len(entries), "truncated": truncated}
    except Exception as exc:
        return error_result(exc)


async def get_recent_commits(repo_url: str, max_results: int = 20) -> dict:
    """Return recent commit summaries, capped at 100 results."""
    try:
        if not 1 <= max_results <= 100:
            return {"error": {"type": "invalid_input", "message": "max_results must be between 1 and 100."}}
        async with github_for_url(repo_url, "get_recent_commits") as (client, owner, repo):
            return {"commits": await client.commits(owner, repo, max_results)}
    except Exception as exc:
        return error_result(exc)
