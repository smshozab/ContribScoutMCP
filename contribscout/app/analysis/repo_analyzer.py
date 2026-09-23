import asyncio

from ..config import get_settings
from ..github.client import GitHubClient

HIGH_SIGNAL = {"readme.md", "readme.rst", "readme", "contributing.md", "contributing.rst", "code_of_conduct.md", "package.json", "pyproject.toml", "requirements.txt", "pipfile", "cargo.toml", "go.mod", "pom.xml", "build.gradle", "gemfile", "composer.json", "dockerfile", "docker-compose.yml", "makefile"}
GUIDES = {"contributing.md", "contributing.rst"}


async def analyze_repository(client: GitHubClient, owner: str, repo: str) -> dict:
    repository = await client.repository(owner, repo)
    tree, truncated = await client.tree(owner, repo, repository.default_branch)
    paths = [entry.path for entry in tree if entry.type == "blob"]
    wanted = [p for p in paths if p.rsplit("/", 1)[-1].lower() in HIGH_SIGNAL and "/" not in p]
    contents = await asyncio.gather(*(client.file(owner, repo, path) for path in wanted), return_exceptions=True)
    files = {path: content for path, content in zip(wanted, contents) if isinstance(content, str)}
    from .stack_detector import detect_stack
    manifest_texts = {p: c for p, c in files.items() if p.rsplit("/", 1)[-1].lower() not in {"readme.md", "readme.rst", "readme", "contributing.md", "contributing.rst"}}
    stack = detect_stack(paths, repository.primary_language, manifest_texts)
    readme = next((c for p, c in files.items() if p.rsplit("/", 1)[-1].lower() in {"readme.md", "readme.rst", "readme"}), "")
    major_dirs = sorted({p.split("/", 1)[0] for p in paths if "/" in p and not p.split("/", 1)[0].startswith(".")})[:30]
    purpose = repository.description or next((line.strip(" #") for line in readme.splitlines() if line.strip() and not line.startswith("![")), "Purpose not stated in repository metadata or README.")
    return {"owner": owner, "repo": repo, "purpose": purpose[:1000], **stack, "major_directories": major_dirs, "contribution_guidelines_present": any(p.rsplit("/", 1)[-1].lower() in GUIDES for p in paths), "setup_files": sorted(p for p in paths if p.rsplit("/", 1)[-1].lower() in HIGH_SIGNAL), "readme_present": bool(readme), "readme": readme[:12000], "contributing": next((c[:12000] for p, c in files.items() if p.rsplit("/", 1)[-1].lower() in GUIDES), None), "paths": paths, "tree_truncated": truncated, "repository": repository.model_dump()}
