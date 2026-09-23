---
name: contribution-scout
description: Find evidence-backed contribution opportunities in public GitHub repositories using the ContribScout MCP tools.
---

# ContribScout contribution scouting

When a GitHub repository URL is provided:

1. Call `get_repository` and `analyze_repository` to understand metadata, README, contribution guidance, stack, and project structure.
2. Call `get_repository_tree` when likely file locations or project shape need inspection. Use `get_file` for a small number of relevant files.
3. Inspect open issues with `list_issues` and pull requests with `list_pull_requests`. Use `get_issue` when evaluating a specific issue.
4. Call `search_repository_markers` and `find_contribution_opportunities` to identify code markers and potential test/documentation gaps.
5. Keep the source distinction explicit: `OFFICIAL_ISSUE` means an existing GitHub issue; `DISCOVERED_OPPORTUNITY` is inferred by ContribScout and is not a maintainer request.
6. Prefer issues without an assignee or active related PR, but describe competition evidence and uncertainty.
7. Use skills and experience the user provides in the current request or conversation to explain matches and mismatches. The MCP server receives only tool arguments; do not claim it can read or retrieve the user's ChatGPT history, saved memories, or past work. Do not silently exclude useful opportunities because of a skill mismatch.
8. Treat difficulty, clarity, scope, and suitability as heuristics. Cite the concrete evidence returned by the tools and do not imply the scoring is objective.
9. Before recommending that someone begin an official issue, call `pre_contribution_check`. Do not claim the contribution will be accepted. Recommend asking maintainers first when scope or assignment expectations are unclear.
10. Call `build_contribution_plan` for an implementation roadmap. Use only existing paths or explicitly identified proposed new files; do not invent code references.

## Suggested response format

### Repository Summary

Summarize purpose, stack, architecture, and contribution guidance.

### Best Contribution Opportunities

For each opportunity, include its source type, difficulty, why it matters, why it may suit the user, evidence, likely files, and current assignment/PR status. Clearly label inferred work as a discovered opportunity.

### Recommended First Contribution

Recommend one opportunity and explain the evidence behind the choice.

### Implementation Roadmap

Give a short, sequenced plan with tests, relevant files, risks, and maintainer questions. Never promise acceptance.
