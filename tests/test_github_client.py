import httpx
import pytest

from contribscout.app.config import Settings
from contribscout.app.github.client import GitHubClient
from contribscout.app.github.exceptions import GitHubError


@pytest.mark.asyncio
async def test_repository_normalization_and_auth_header():
    seen = {}
    def handler(request):
        seen.update(dict(request.headers))
        return httpx.Response(200, json={"name": "sample", "owner": {"login": "acme"}, "stargazers_count": 5, "topics": ["python"], "license": {"spdx_id": "MIT"}, "default_branch": "main", "html_url": "https://github.com/acme/sample"})
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.test", headers={"Authorization": "Bearer secret", "User-Agent": "ContribScout/0.1.0"})
    client = GitHubClient(Settings(github_token="secret", github_api_url="https://api.github.test"), http)
    repo = await client.repository("acme", "sample")
    assert repo.owner == "acme" and repo.stars == 5 and repo.license == "MIT"
    assert seen["authorization"] == "Bearer secret"
    await http.aclose()


@pytest.mark.asyncio
async def test_issues_filter_pull_requests():
    payload = [{"number": 1, "title": "issue", "labels": [], "assignees": [], "state": "open", "html_url": "i"}, {"number": 2, "title": "pr", "pull_request": {}, "labels": [], "assignees": [], "state": "open", "html_url": "p"}]
    def handler(request):
        if request.url.path == "/repos/acme/sample":
            return httpx.Response(200, json={"name": "sample", "owner": {"login": "acme"}, "default_branch": "main"})
        return httpx.Response(200, json=payload)
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.test")
    client = GitHubClient(Settings(github_api_url="https://api.github.test"), http)
    issues = await client.issues("acme", "sample")
    assert [x.number for x in issues] == [1]
    await http.aclose()


@pytest.mark.asyncio
async def test_missing_resource_maps_to_safe_error():
    def handler(request):
        if request.url.path == "/repos/acme/sample":
            return httpx.Response(200, json={"name": "sample", "owner": {"login": "acme"}, "default_branch": "main"})
        return httpx.Response(404, json={"message": "Not Found"})
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.test")
    client = GitHubClient(Settings(github_api_url="https://api.github.test"), http)
    with pytest.raises(GitHubError) as caught:
        await client.file("acme", "sample", "absent.txt")
    assert caught.value.kind == "not_found"
    assert "not found" in str(caught.value).lower()
    await http.aclose()


@pytest.mark.asyncio
async def test_empty_repository_has_empty_tree_not_an_api_failure():
    payload = {"name": "empty", "owner": {"login": "acme"}, "html_url": "https://github.com/acme/empty", "default_branch": None}
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)), base_url="https://api.github.test")
    client = GitHubClient(Settings(github_api_url="https://api.github.test"), http)
    entries, truncated = await client.tree("acme", "empty")
    assert entries == [] and not truncated
    await http.aclose()


@pytest.mark.asyncio
async def test_transient_protocol_disconnect_is_retried():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.RemoteProtocolError("server disconnected")
        return httpx.Response(200, json={"name": "sample", "owner": {"login": "acme"}, "html_url": "https://github.com/acme/sample", "default_branch": "main"})
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.test")
    client = GitHubClient(Settings(github_api_url="https://api.github.test"), http)
    result = await client.repository("acme", "sample")
    assert result.name == "sample" and calls == 2
    await http.aclose()


@pytest.mark.asyncio
async def test_private_repository_is_rejected_before_listing_issues():
    paths = []
    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"name": "sample", "owner": {"login": "acme"}, "private": True})
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.test")
    client = GitHubClient(Settings(github_api_url="https://api.github.test"), http)
    with pytest.raises(GitHubError) as caught:
        await client.issues("acme", "sample")
    assert caught.value.kind == "private_repository"
    assert paths == ["/repos/acme/sample"]
    await http.aclose()
