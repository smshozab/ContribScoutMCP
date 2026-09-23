from ...config import get_settings
from .common import error_result, github_for_url


async def list_issues(repo_url: str, labels: str | None = None, state: str = "open", max_results: int = 30) -> dict:
    """List genuine GitHub issues; pull requests in the Issues API are excluded."""
    if state not in {"open", "closed", "all"} or not 1 <= max_results <= 100:
        return {"error": {"type": "invalid_input", "message": "state must be open, closed, or all; max_results must be 1-100."}}
    try:
        async with github_for_url(repo_url, "list_issues") as (client, owner, repo):
            issues = await client.issues(owner, repo, state, labels, min(max_results, get_settings().max_issues))
            return {"issues": [x.model_dump() for x in issues], "count": len(issues)}
    except Exception as exc:
        return error_result(exc)


async def get_issue(repo_url: str, issue_number: int) -> dict:
    """Fetch one issue with its recent comment details and metadata."""
    if issue_number < 1:
        return {"error": {"type": "invalid_input", "message": "issue_number must be positive."}}
    try:
        async with github_for_url(repo_url, "get_issue") as (client, owner, repo):
            issue = await client.issue(owner, repo, issue_number)
            comments = await client.comments(owner, repo, issue_number)
            return {**issue.model_dump(), "comment_details": [{"author": (x.get("user") or {}).get("login"), "body": x.get("body"), "created_at": x.get("created_at"), "updated_at": x.get("updated_at"), "url": x.get("html_url")} for x in comments]}
    except Exception as exc:
        return error_result(exc)
