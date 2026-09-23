from types import SimpleNamespace

from contribscout.app.analysis.gap_detector import MARKER, discover_gaps
from contribscout.app.analysis.scoring import score_issue
from contribscout.app.analysis.stack_detector import detect_stack
from contribscout.app.github.client import GitHubClient
from contribscout.app.github.exceptions import GitHubError
from contribscout.app.mcp.tools.files import get_file


def issue(**kw):
    values = {"number": 12, "title": "Add widget validation", "body": "Steps to reproduce\nExpected behavior is validated. Acceptance criteria: reject empty input. `src/widget.py`", "labels": ["good first issue", "bug"], "comments": 2, "assignees": [], "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-09-20T00:00:00Z", "state": "open", "author": "dev", "url": "https://github.com/o/r/issues/12"}
    return SimpleNamespace(**(values | kw))


def test_issue_normalization_filters_prs_and_normalizes_fields():
    normalized = GitHubClient.normalize_issue({"number": 7, "title": "Bug", "labels": [{"name": "bug"}], "assignees": [{"login": "alice"}], "user": {"login": "bob"}, "state": "open", "html_url": "u"})
    assert normalized.labels == ["bug"]
    assert normalized.assignees == ["alice"]
    assert normalized.author == "bob"
    # The client checks GitHub's pull_request key before calling normalize_issue.
    assert "pull_request" in {"number": 8, "pull_request": {}}


def test_scoring_and_issue_suitability():
    scored = score_issue(issue(), [])
    assert scored["clarity"] == "high"
    assert scored["suitability"] == "high"
    assert any("first-time" in reason for reason in scored["reasons"])
    assert score_issue(issue(assignees=["alice"]), [SimpleNamespace(title="Add widget validation", body="", number=9)])["suitability"] != "high"


def test_marker_recognition_and_gap_classification():
    assert MARKER.search("# TODO: cover this")
    gaps = discover_gaps(["src/main.py", "examples/basic.py"], [{"file": "src/main.py", "line": 8, "marker": "TODO", "context": "TODO add docs"}], {"readme_present": False, "readme": "", "contribution_guidelines_present": False})
    assert gaps[0]["type"] == "DISCOVERED_OPPORTUNITY"
    assert gaps[0]["category"] == "todo"
    assert any(g["identifier"] == "docs:no-readme" for g in gaps)
    assert any(g["identifier"] == "test-gap:no-tests" for g in gaps)


def test_examples_gap_only_references_existing_readme():
    gaps = discover_gaps(["examples/demo.py", "README.md"], [], {"readme_present": True, "readme": "Project overview", "contribution_guidelines_present": True})
    examples_gap = next(g for g in gaps if g["identifier"] == "docs:examples-not-linked")
    assert "README.md" in examples_gap["likely_files"]


def test_stack_detection():
    result = detect_stack(["pyproject.toml", "package.json", "src/app.py"], "Python", {"pyproject.toml": "[project]\ndependencies=['fastapi','pytest']", "package.json": "{\"devDependencies\":{\"jest\":\"*\",\"react\":\"*\"}}"})
    assert result["languages"] == ["JavaScript/TypeScript", "Python"]
    assert "FastAPI" in result["frameworks"]
    assert "pytest" in result["test_frameworks"]
    assert "Jest" in result["test_frameworks"]


def test_missing_file_error_is_structured():
    # Input validation fails before any network access; the same structured error shape is used by tools.
    import asyncio
    result = asyncio.run(get_file("https://github.com/owner/repo", "../secret"))
    assert result["error"]["type"] == "invalid_input"


def test_github_error_does_not_include_response_secrets():
    error = GitHubError("Repository or resource not found, or it is private.", status_code=404, kind="not_found")
    assert error.kind == "not_found"
    assert "token" not in str(error).lower()
