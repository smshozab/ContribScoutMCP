from .issue_analyzer import analyze_issue


def score_issue(issue, prs: list) -> dict:
    analysis = analyze_issue(issue, prs)
    labels = {x.lower() for x in issue.labels}
    score = 35
    if labels & {"good first issue", "good-first-issue"}: score += 20
    if "help wanted" in labels: score += 15
    if not issue.assignees: score += 10
    if analysis["recently_updated"]: score += 10
    score += {"high": 15, "medium": 8, "low": 0}[analysis["clarity"]]
    if analysis["scope"] == "small": score += 10
    if analysis["active_related_pr"]: score -= 35
    if issue.assignees: score -= 18
    if analysis["clarity"] == "low": score -= 15
    if analysis["scope"] == "large": score -= 15
    if issue.comments == 0 and not (issue.body or "").strip(): score -= 15
    score = max(0, min(100, score))
    category = "HIGH" if score >= 70 else "MEDIUM" if score >= 45 else "LOW" if score < 30 else "UNCERTAIN"
    return {**analysis, "suitability": category.lower(), "reasons": analysis["reasons"] + [f"heuristic suitability category: {category.lower()} (not an objective measure)"]}
