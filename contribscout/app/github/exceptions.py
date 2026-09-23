class GitHubError(Exception):
    """Safe, user-facing GitHub API failure."""

    def __init__(self, message: str, *, status_code: int | None = None, kind: str = "github_error") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.kind = kind


class InvalidRepositoryURL(ValueError):
    pass
