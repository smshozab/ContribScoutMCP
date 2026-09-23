from pydantic import BaseModel


class Issue(BaseModel):
    number: int
    title: str
    body: str | None = None
    labels: list[str] = []
    comments: int = 0
    assignees: list[str] = []
    created_at: str | None = None
    updated_at: str | None = None
    state: str
    author: str | None = None
    url: str


class PullRequest(BaseModel):
    number: int
    title: str
    body: str | None = None
    author: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    draft: bool = False
    head_branch: str
    base_branch: str
    url: str
