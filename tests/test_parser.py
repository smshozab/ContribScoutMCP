import pytest

from contribscout.app.github.exceptions import InvalidRepositoryURL
from contribscout.app.github.parser import parse_repository_url


@pytest.mark.parametrize("url", ["https://github.com/owner/repo", "https://github.com/owner/repo/", "https://github.com/owner/repo.git", "git@github.com:owner/repo.git"])
def test_parse_supported_urls(url):
    assert parse_repository_url(url) == ("owner", "repo")


@pytest.mark.parametrize("url", ["", "https://gitlab.com/owner/repo", "https://github.com/owner", "https://github.com/owner/repo/issues", "https://github.com.evil.test/owner/repo", "https://user@github.com/owner/repo", "github.com/owner/repo"])
def test_reject_invalid_urls(url):
    with pytest.raises(InvalidRepositoryURL):
        parse_repository_url(url)
