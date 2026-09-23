from ...analysis.gap_detector import scan_markers
from ...config import get_settings
from .common import error_result, github_for_url


async def get_file(repo_url: str, file_path: str) -> dict:
    """Read one bounded UTF-8 text file from a public repository."""
    if not file_path or file_path.startswith("/") or ".." in file_path.split("/"):
        return {"error": {"type": "invalid_input", "message": "file_path must be a repository-relative path."}}
    try:
        async with github_for_url(repo_url, "get_file") as (client, owner, repo):
            return {"path": file_path, "content": await client.file(owner, repo, file_path)}
    except Exception as exc:
        return error_result(exc)


async def search_repository_markers(repo_url: str) -> dict:
    """Scan a bounded set of source/text files for TODO and similar markers."""
    try:
        async with github_for_url(repo_url, "search_repository_markers") as (client, owner, repo):
            entries, truncated = await client.tree(owner, repo)
            settings = get_settings()
            markers = await scan_markers(client, owner, repo, [x.path for x in entries if x.type == "blob"], settings.max_files_to_scan, settings.max_file_size)
            return {"markers": markers, "count": len(markers), "files_considered_limit": settings.max_files_to_scan, "tree_truncated": truncated}
    except Exception as exc:
        return error_result(exc)
