import re
import time

from ...analysis.gap_detector import discover_gaps, scan_markers
from ...analysis.issue_analyzer import analyze_issue
from ...analysis.repo_analyzer import analyze_repository
from ...analysis.scoring import score_issue
from ...config import get_settings
from .common import error_result, github_for_url, logger


async def analyze_repository_tool(repo_url: str) -> dict:
    """Summarize repository purpose, stack, structure, README, and contribution guidance."""
    started = time.monotonic()
    try:
        async with github_for_url(repo_url, "analyze_repository") as (client, owner, repo):
            result = await analyze_repository(client, owner, repo)
            logger.info("repository analysis completed owner=%s repo=%s duration_ms=%d", owner, repo, int((time.monotonic()-started)*1000))
            return {k: v for k, v in result.items() if k != "paths"}
    except Exception as exc:
        return error_result(exc)


def _difficulty(issue) -> str:
    labels = {x.lower() for x in issue.labels}
    body = (issue.body or "").lower()
    if labels & {"good first issue", "good-first-issue"} or "documentation" in labels: return "easy"
    if any(x in body for x in ["architecture", "rewrite", "migration", "across the project"]): return "hard"
    if not body or len(body) < 80: return "uncertain"
    return "medium"


def _skills_for(text: str, available: list[str]) -> list[str]:
    lower = text.lower()
    return [skill for skill in available if skill.lower() in lower]


async def find_contribution_opportunities(repo_url: str, skills: list[str] | None = None, preferred_difficulty: str | None = None, max_results: int = 10) -> dict:
    """Rank official issues and clearly separated, heuristic repository-gap opportunities."""
    if not 1 <= max_results <= 50 or (preferred_difficulty and preferred_difficulty not in {"easy", "medium", "hard", "uncertain"}):
        return {"error": {"type": "invalid_input", "message": "max_results must be 1-50 and preferred_difficulty must be easy, medium, hard, or uncertain."}}
    started = time.monotonic()
    try:
        async with github_for_url(repo_url, "find_contribution_opportunities") as (client, owner, repo):
            settings = get_settings()
            overview = await analyze_repository(client, owner, repo)
            issues = await client.issues(owner, repo, "open", limit=settings.max_issues)
            prs = await client.pull_requests(owner, repo, "open", limit=settings.max_prs)
            markers = await scan_markers(client, owner, repo, overview["paths"], settings.max_files_to_scan, settings.max_file_size)
            gaps = discover_gaps(overview["paths"], markers, overview)
            candidates = []
            for issue in issues:
                scored = score_issue(issue, prs)
                difficulty = _difficulty(issue)
                text = f"{issue.title}\n{issue.body or ''}"
                candidates.append({"source_type": "OFFICIAL_ISSUE", "title": issue.title, "description": (issue.body or "No issue description provided.")[:3000], "difficulty": difficulty, "suitability": scored["suitability"], "skills": _skills_for(text, skills or []), "likely_files": re.findall(r"(?:[\w.-]+/)*[\w.-]+\.(?:py|ts|tsx|js|jsx|go|rs|md)", text)[:10], "evidence": scored["reasons"], "warnings": (["Issue has an assignee."] if issue.assignees else []) + (["A possibly related open PR exists."] if scored["active_related_pr"] else []), "github_issue_number": issue.number, "github_url": issue.url, "_rank": {"high": 4, "medium": 3, "uncertain": 2, "low": 1}.get(scored["suitability"], 0)})
            for gap in gaps:
                skill_matches = _skills_for(" ".join(gap["evidence"] + gap["likely_files"] + [gap["category"]]), skills or [])
                candidates.append({"source_type": "DISCOVERED_OPPORTUNITY", "title": gap["title"], "description": gap["recommended_action"], "difficulty": "easy" if gap["category"] in {"todo", "documentation"} else "medium", "suitability": "medium" if gap["confidence"] != "low" else "uncertain", "skills": skill_matches, "likely_files": gap["likely_files"], "evidence": gap["evidence"], "warnings": ["Inferred by deterministic heuristics; this is not an official maintainer request."] + (["No provided skill matched this opportunity."] if skills and not skill_matches else []), "github_issue_number": None, "github_url": None, "identifier": gap["identifier"], "_rank": 2})
            if skills:
                for item in candidates:
                    item["warnings"].extend([] if item["skills"] else ["No provided skill matched; included because it may still be useful."])
            if preferred_difficulty:
                preferred = [x for x in candidates if x["difficulty"] == preferred_difficulty]
                candidates = preferred + [x for x in candidates if x["difficulty"] != preferred_difficulty]
            candidates.sort(key=lambda x: x["_rank"], reverse=True)
            for candidate in candidates: candidate.pop("_rank", None)
            result = {"repository": {"owner": owner, "repo": repo, "description": overview["purpose"], "languages": overview["languages"], "frameworks": overview["frameworks"]}, "contribution_guidelines_present": overview["contribution_guidelines_present"], "opportunities": candidates[:max_results], "count": min(max_results, len(candidates)), "source_counts": {"official_issues": len(issues), "discovered_opportunities": len(gaps)}, "heuristic_notice": "Suitability, difficulty, and gap findings are estimates based on observable repository evidence."}
            logger.info("opportunity analysis completed owner=%s repo=%s duration_ms=%d", owner, repo, int((time.monotonic()-started)*1000))
            return result
    except Exception as exc:
        return error_result(exc)


async def pre_contribution_check(repo_url: str, issue_number: int) -> dict:
    """Refresh issue status, assignees, comments, possible competing PRs, and guidance."""
    if issue_number < 1:
        return {"error": {"type": "invalid_input", "message": "issue_number must be positive."}}
    try:
        async with github_for_url(repo_url, "pre_contribution_check") as (client, owner, repo):
            issue = await client.issue(owner, repo, issue_number)
            comments = await client.comments(owner, repo, issue_number, limit=30)
            prs = await client.pull_requests(owner, repo, "open", limit=get_settings().max_prs)
            overview = await analyze_repository(client, owner, repo)
            related = [p for p in prs if f"#{issue_number}" in (p.title + " " + (p.body or "")) or issue.title.lower() in p.title.lower()]
            comment_text = "\n".join((c.get("body") or "") for c in comments).lower()
            issue_text = (issue.body or "").lower()
            asks_assignment = any(term in issue_text + " " + comment_text for term in ["assign me", "request to be assigned", "please wait for assignment", "wait until assigned", "comment to be assigned"])
            warnings = []
            if issue.state != "open": warnings.append("Issue is no longer open.")
            if issue.assignees: warnings.append("Issue currently has assignee(s): " + ", ".join(issue.assignees))
            if related: warnings.append("Possible related open pull request(s): " + ", ".join(f"#{p.number}" for p in related))
            if not overview["contribution_guidelines_present"]: warnings.append("No root CONTRIBUTING.md or CONTRIBUTING.rst was found.")
            if asks_assignment: warnings.append("Issue text/comments indicate assignment or maintainer coordination may be expected.")
            updated_recently = False
            if issue.updated_at:
                from datetime import datetime, timezone
                updated_recently = (datetime.now(timezone.utc) - datetime.fromisoformat(issue.updated_at.replace("Z", "+00:00"))).days <= 7
            if updated_recently: warnings.append("Issue was updated in the last 7 days; review recent activity before starting.")
            next_step = "Ask maintainers whether they want this work and request assignment before substantial implementation." if asks_assignment or related or issue.assignees else "Read the contribution guidance, review recent discussion, and leave a concise issue comment describing your intended approach if coordination is unclear."
            return {"issue_number": issue_number, "state": issue.state, "assignees": issue.assignees, "recent_comments": [{"author": (c.get("user") or {}).get("login"), "body": (c.get("body") or "")[:1000], "created_at": c.get("created_at")} for c in comments[-10:]], "active_related_prs": [{"number": p.number, "title": p.title, "url": p.url} for p in related], "contribution_guidelines_present": overview["contribution_guidelines_present"], "guidelines_excerpt": (overview.get("contributing") or "")[:2500], "assignment_requested_or_indicated": asks_assignment, "updated_within_7_days": updated_recently, "safe_to_start": issue.state == "open" and not issue.assignees and not related and not asks_assignment, "warnings": warnings + ["This check is heuristic and does not guarantee maintainer acceptance."], "recommended_next_step": next_step}
    except Exception as exc:
        return error_result(exc)


async def build_contribution_plan(repo_url: str, issue_number: int | None = None, opportunity_id: str | None = None) -> dict:
    """Build an evidence-based roadmap for exactly one official issue or discovered opportunity."""
    if (issue_number is None) == (opportunity_id is None):
        return {"error": {"type": "invalid_input", "message": "Provide exactly one of issue_number or opportunity_id."}}
    try:
        async with github_for_url(repo_url, "build_contribution_plan") as (client, owner, repo):
            overview = await analyze_repository(client, owner, repo)
            issue = None
            if issue_number is not None:
                if issue_number < 1: return {"error": {"type": "invalid_input", "message": "issue_number must be positive."}}
                issue = await client.issue(owner, repo, issue_number)
                title = issue.title
                problem = (issue.body or "No problem statement provided.")[:2500]
                evidence = [f"Official GitHub issue #{issue.number}: {issue.url}"]
                file_refs = re.findall(r"(?:[\w.-]+/)*[\w.-]+\.(?:py|ts|tsx|js|jsx|go|rs|md)", issue.body or "")
                source_type = "OFFICIAL_ISSUE"
                warnings = ["Confirm the issue is still open and coordinate with maintainers before substantial work."]
                questions = ["Is the proposed behavior and scope still desired?", "Are there implementation constraints or compatibility requirements?"]
                branch_fragment = f"issue-{issue.number}"
                tests = ["Add or update focused tests for the requested behavior.", "Run the repository's documented test command, if available."]
            else:
                paths = overview["paths"]
                markers = await scan_markers(client, owner, repo, paths, get_settings().max_files_to_scan, get_settings().max_file_size)
                gaps = discover_gaps(paths, markers, overview)
                gap = next((g for g in gaps if g["identifier"] == opportunity_id), None)
                if not gap: return {"error": {"type": "not_found", "message": "Opportunity identifier is not present in the current repository scan."}}
                title = gap["title"]
                problem = gap["recommended_action"]
                evidence = gap["evidence"]
                file_refs = gap["likely_files"]
                source_type = "DISCOVERED_OPPORTUNITY"
                warnings = ["This is a ContribScout inference, not an official maintainer request. Ask maintainers whether the change is wanted."]
                questions = ["Would maintainers like this opportunity addressed?", "What scope and testing expectations should the contribution follow?"]
                branch_fragment = re.sub(r"[^a-z0-9-]+", "-", title.lower()).strip("-")[:35]
                tests = ["Add focused regression tests for any behavior changed.", "Run existing checks documented in the repository."]
            existing = [p for p in overview["paths"] if p in file_refs]
            proposed = [p for p in file_refs if p not in existing]
            modules = sorted({p.split("/", 1)[0] for p in existing if "/" in p})
            sequence = ["Read the contribution guidelines and inspect the cited files and nearby tests.", "Confirm desired scope with maintainers if the issue or inferred gap is ambiguous.", "Implement the smallest change that addresses the evidence.", "Add or update focused tests and documentation where applicable.", "Run project checks, review the diff, and open a pull request following repository guidance."]
            return {"source_type": source_type, "title": title, "problem_summary": problem, "relevant_repository_areas": modules, "likely_files_to_inspect": existing, "proposed_new_files": proposed, "implementation_sequence": sequence, "tests_to_add_or_run": tests, "contribution_guidelines": (overview.get("contributing") or "No root contribution guide found.")[:4000], "risks": warnings, "questions_for_maintainers": questions, "suggested_branch_name": f"contribscout/{branch_fragment}", "suggested_pr_title": title[:100], "evidence": evidence, "acceptance_not_guaranteed": True}
    except Exception as exc:
        return error_result(exc)
