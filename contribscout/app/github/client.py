import asyncio
import base64
import logging
import random
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import Settings, get_settings
from ..models.issue import Issue, PullRequest
from ..models.repository import Repository, TreeEntry
from .exceptions import GitHubError

logger = logging.getLogger("contribscout.github")


class GitHubClient:
    """Small async REST client with bounded retries and normalized models."""

    def __init__(self, settings: Settings | None = None, http_client: httpx.AsyncClient | None = None):
        self.settings = settings or get_settings()
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "ContribScout/0.1.0", "X-GitHub-Api-Version": "2022-11-28"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        self._client = http_client or httpx.AsyncClient(base_url=self.settings.github_api_url.rstrip("/"), headers=headers, timeout=self.settings.request_timeout_seconds)
        self._owns_client = http_client is None
        self._public_repositories: set[tuple[str, str]] = set()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        for attempt in range(3):
            try:
                response = await self._client.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt < 2:
                    await asyncio.sleep(0.25 * (2**attempt) + random.random() * 0.1)
                    continue
                logger.warning("GitHub network request failed")
                raise GitHubError("GitHub is temporarily unavailable. Please try again.", kind="unavailable") from exc
            if response.status_code >= 500 and attempt < 2:
                await asyncio.sleep(0.25 * (2**attempt) + random.random() * 0.1)
                continue
            if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
                reset = response.headers.get("X-RateLimit-Reset")
                when = "unknown"
                if reset and reset.isdigit():
                    when = datetime.fromtimestamp(int(reset), timezone.utc).isoformat()
                logger.warning("GitHub API rate limit reached; reset=%s", when)
                raise GitHubError(f"GitHub API rate limit reached. Reset time: {when}.", status_code=403, kind="rate_limit")
            if response.status_code >= 400:
                kinds = {404: ("Repository or resource not found, or it is private.", "not_found"), 401: ("GitHub authorization failed.", "unauthorized"), 403: ("GitHub denied the request. Check token permissions or API limits.", "forbidden")}
                message, kind = kinds.get(response.status_code, (f"GitHub API request failed with status {response.status_code}.", "github_error"))
                logger.warning("GitHub API error status=%s path=%s", response.status_code, path)
                raise GitHubError(message, status_code=response.status_code, kind=kind)
            try:
                return response.json()
            except ValueError as exc:
                raise GitHubError("GitHub returned an invalid response.", kind="invalid_response") from exc
        raise GitHubError("GitHub request failed after retries.", kind="unavailable")

    async def _paginate(self, path: str, params: dict[str, Any] | None = None, limit: int = 100) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        page = 1
        while len(result) < limit:
            query = {**(params or {}), "per_page": min(100, limit - len(result)), "page": page}
            data = await self._request(path, query)
            if not isinstance(data, list) or not data:
                break
            result.extend(item for item in data if isinstance(item, dict))
            if len(data) < query["per_page"]:
                break
            page += 1
        return result[:limit]

    async def repository(self, owner: str, repo: str) -> Repository:
        d = await self._request(f"/repos/{owner}/{repo}")
        if not isinstance(d, dict):
            raise GitHubError("GitHub returned an invalid repository response.", kind="invalid_response")
        if d.get("private") is True:
            raise GitHubError("ContribScout supports public repositories only.", kind="private_repository")
        self._public_repositories.add((owner.casefold(), repo.casefold()))
        return Repository(owner=d.get("owner", {}).get("login", owner), name=d.get("name", repo), description=d.get("description"), stars=d.get("stargazers_count", 0), forks=d.get("forks_count", 0), primary_language=d.get("language"), topics=d.get("topics", []), default_branch=d.get("default_branch"), open_issues_count=d.get("open_issues_count", 0), license=(d.get("license") or {}).get("spdx_id"), created_at=d.get("created_at"), updated_at=d.get("updated_at"), homepage=d.get("homepage") or None, archived=d.get("archived", False), html_url=d.get("html_url", f"https://github.com/{owner}/{repo}"))

    async def _ensure_public(self, owner: str, repo: str) -> None:
        if (owner.casefold(), repo.casefold()) not in self._public_repositories:
            await self.repository(owner, repo)

    async def tree(self, owner: str, repo: str, branch: str | None = None) -> tuple[list[TreeEntry], bool]:
        branch = branch or (await self.repository(owner, repo)).default_branch
        if not branch:
            return [], False
        ref = await self._request(f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
        sha = ref["object"]["sha"]
        data = await self._request(f"/repos/{owner}/{repo}/git/trees/{sha}", {"recursive": "1"})
        return [TreeEntry(path=x["path"], type=x["type"], size=x.get("size"), sha=x.get("sha")) for x in data.get("tree", []) if x.get("type") in {"blob", "tree"}], bool(data.get("truncated"))

    async def file(self, owner: str, repo: str, path: str) -> str:
        await self._ensure_public(owner, repo)
        # Contents endpoint is convenient, but reject large blobs before decoding.
        data = await self._request(f"/repos/{owner}/{repo}/contents/{path}")
        if isinstance(data, list):
            raise GitHubError("The requested path is a directory, not a file.", kind="not_file")
        if data.get("size", 0) > self.settings.max_file_size:
            raise GitHubError(f"File is too large to return (limit: {self.settings.max_file_size} bytes).", kind="too_large")
        if data.get("encoding") != "base64" or not data.get("content"):
            raise GitHubError("File is binary or GitHub did not provide text content.", kind="binary")
        try:
            return base64.b64decode(data["content"], validate=False).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise GitHubError("File is binary or is not valid UTF-8 text.", kind="binary") from exc

    async def issues(self, owner: str, repo: str, state: str = "open", labels: str | None = None, limit: int = 100) -> list[Issue]:
        await self._ensure_public(owner, repo)
        params: dict[str, Any] = {"state": state}
        if labels:
            params["labels"] = labels
        data = await self._paginate(f"/repos/{owner}/{repo}/issues", params, limit)
        return [self.normalize_issue(x) for x in data if "pull_request" not in x]

    @staticmethod
    def normalize_issue(d: dict[str, Any]) -> Issue:
        return Issue(number=d["number"], title=d.get("title", ""), body=d.get("body"), labels=[x.get("name", "") for x in d.get("labels", [])], comments=d.get("comments", 0), assignees=[x.get("login", "") for x in d.get("assignees", [])], created_at=d.get("created_at"), updated_at=d.get("updated_at"), state=d.get("state", "open"), author=(d.get("user") or {}).get("login"), url=d.get("html_url", ""))

    async def issue(self, owner: str, repo: str, number: int) -> Issue:
        await self._ensure_public(owner, repo)
        return self.normalize_issue(await self._request(f"/repos/{owner}/{repo}/issues/{number}"))

    async def comments(self, owner: str, repo: str, number: int, limit: int = 100) -> list[dict[str, Any]]:
        await self._ensure_public(owner, repo)
        return await self._paginate(f"/repos/{owner}/{repo}/issues/{number}/comments", limit=limit)

    async def pull_requests(self, owner: str, repo: str, state: str = "open", limit: int = 100) -> list[PullRequest]:
        await self._ensure_public(owner, repo)
        data = await self._paginate(f"/repos/{owner}/{repo}/pulls", {"state": state, "sort": "updated", "direction": "desc"}, limit)
        return [PullRequest(number=x["number"], title=x.get("title", ""), body=x.get("body"), author=(x.get("user") or {}).get("login"), created_at=x.get("created_at"), updated_at=x.get("updated_at"), draft=x.get("draft", False), head_branch=(x.get("head") or {}).get("ref", ""), base_branch=(x.get("base") or {}).get("ref", ""), url=x.get("html_url", "")) for x in data]

    async def commits(self, owner: str, repo: str, limit: int = 20) -> list[dict[str, Any]]:
        await self._ensure_public(owner, repo)
        data = await self._paginate(f"/repos/{owner}/{repo}/commits", limit=limit)
        return [{"sha": x.get("sha"), "message": (x.get("commit") or {}).get("message", "").splitlines()[0], "author": ((x.get("author") or {}).get("login") or (x.get("commit") or {}).get("author", {}).get("name")), "date": (x.get("commit") or {}).get("author", {}).get("date"), "url": x.get("html_url")} for x in data]

    async def languages(self, owner: str, repo: str) -> dict[str, int]:
        await self._ensure_public(owner, repo)
        return await self._request(f"/repos/{owner}/{repo}/languages")
