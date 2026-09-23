from pydantic import BaseModel


class Repository(BaseModel):
    owner: str
    name: str
    description: str | None = None
    stars: int = 0
    forks: int = 0
    primary_language: str | None = None
    topics: list[str] = []
    default_branch: str | None = None
    open_issues_count: int = 0
    license: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    homepage: str | None = None
    archived: bool = False
    html_url: str


class TreeEntry(BaseModel):
    path: str
    type: str
    size: int | None = None
    sha: str | None = None
