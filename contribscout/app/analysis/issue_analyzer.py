from datetime import datetime, timezone


def analyze_issue(issue, prs: list, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    body = (issue.body or "").lower()
    labels = [x.lower() for x in issue.labels]
    updated = datetime.fromisoformat(issue.updated_at.replace("Z", "+00:00")) if issue.updated_at else None
    days = (now - updated).days if updated else None
    reasons = []
    if any(x in labels for x in ("good first issue", "good-first-issue")): reasons.append("labeled for first-time contributors")
    if "help wanted" in labels: reasons.append("labeled help wanted")
    if not issue.assignees: reasons.append("no assignee")
    else: reasons.append("assigned to " + ", ".join(issue.assignees))
    if days is not None and days <= 30: reasons.append(f"updated {days} days ago")
    elif days is not None and days > 180: reasons.append(f"stale signal: updated {days} days ago")
    repro = any(x in body for x in ["steps to reproduce", "reproduction", "repro:", "minimal example"])
    expected = "expected behavior" in body or "should " in body
    actual = "actual behavior" in body or "instead " in body or "currently " in body
    acceptance = any(x in body for x in ["acceptance criteria", "done when", "success criteria"])
    code_refs = "`" in body or ".py" in body or ".js" in body or "#l" in body
    if repro: reasons.append("description contains reproduction guidance")
    if expected: reasons.append("description states expected behavior")
    if acceptance: reasons.append("description includes acceptance criteria")
    active = [p for p in prs if issue.title.lower() in p.title.lower() or f"#{issue.number}" in (p.title + " " + (p.body or ""))]
    if active: reasons.append("possible related open pull request found")
    scope = "small" if any(x in labels for x in ["good first issue", "good-first-issue", "documentation"]) else "large" if any(x in body for x in ["refactor", "rewrite", "architecture", "across the project"]) else "uncertain"
    clarity = "high" if sum((repro, expected, acceptance, code_refs)) >= 3 else "medium" if sum((repro, expected, acceptance, actual, code_refs)) >= 2 else "low"
    return {"issue_number": issue.number, "clarity": clarity, "scope": scope, "assigned": bool(issue.assignees), "recently_updated": days is not None and days <= 30, "comments": issue.comments, "has_reproduction": repro, "has_expected_behavior": expected, "has_actual_behavior": actual, "has_acceptance_criteria": acceptance, "has_code_references": code_refs, "active_related_pr": bool(active), "reasons": reasons}
