# OpenAI submission test cases

Run these against the deployed HTTPS MCP endpoint after scanning its tools. Record the concrete repository/issue fixture in the portal when running each case; public repositories can change between review runs.

## Positive cases

1. **Repository overview**
   - Prompt: “Analyze `https://github.com/harrymunro/jev-laya-benchmark`. Summarize what it does, its stack, structure, and contribution instructions.”
   - Expected behavior: call `get_repository` and `analyze_repository`; accurately report missing contribution instructions if still absent.
   - Expected result: metadata, purpose, languages/frameworks, major directories, and a boolean for contribution-guideline presence. Do not invent architecture or maintainer guidance.
   - Fixture: public repository URL; no account required.

2. **Repository with no currently open issues**
   - Prompt: “Find contribution opportunities in `https://github.com/harrymunro/jev-laya-benchmark`.”
   - Expected behavior: call `find_contribution_opportunities`; separate official issues from discovered opportunities; gracefully report zero official issues if still true.
   - Expected result: `source_type` is `OFFICIAL_ISSUE` or `DISCOVERED_OPPORTUNITY`; inferred gaps are never presented as maintainer requests.
   - Fixture: public repository URL; no account required.

3. **Official issue suitability**
   - Prompt: “Check whether issue #<OPEN_ISSUE_NUMBER> in <PUBLIC_REPOSITORY_URL> is suitable for a first contribution. Explain the evidence and current competition.”
   - Expected behavior: use `get_issue`, `list_pull_requests`, issue analysis, then `pre_contribution_check` before recommending a start.
   - Expected result: issue status, assignment/PR evidence, heuristic suitability, caveats, and a cautious next step.
   - Fixture: replace placeholders with a currently open issue and public repository URL before submitting.

4. **Marker and gap discovery**
   - Prompt: “Scan `https://github.com/harrymunro/jev-laya-benchmark` for TODOs and potential test or documentation gaps. Tell me which are discovered hypotheses.”
   - Expected behavior: call `search_repository_markers` and/or `find_contribution_opportunities`; use evidence from returned files and paths.
   - Expected result: bounded findings with marker/file/line/context where found; label heuristic gaps as `DISCOVERED_OPPORTUNITY` with confidence and evidence.
   - Fixture: public repository URL; no account required.

5. **Implementation roadmap**
   - Prompt: “Build a contribution plan for issue #<OPEN_ISSUE_NUMBER> in <PUBLIC_REPOSITORY_URL>, including likely files, steps, tests, risks, and questions for maintainers.”
   - Expected behavior: call `build_contribution_plan`; run `pre_contribution_check` first for an official issue.
   - Expected result: structured roadmap using existing files or explicitly proposed new files; never fabricate references or promise acceptance.
   - Fixture: replace placeholders with a currently open issue and public repository URL before submitting.

## Negative cases

1. **Non-GitHub or malformed repository URL**
   - Prompt: “Analyze `https://example.com/acme/project` for contribution opportunities.”
   - Expected behavior: do not query an arbitrary host; return a concise URL validation explanation and request a GitHub repository URL.
   - Why not complete: ContribScout only accepts supported GitHub repository URLs.

2. **Write request**
   - Prompt: “Comment on issue #123 saying I’ll work on it and open a pull request for me.”
   - Expected behavior: explain that the integration is read-only; do not call any write tool or claim an action was taken. It may offer a draft comment or a checklist in text.
   - Why not complete: this server has no GitHub write capability and must not imply it does.

3. **Private repository**
   - Prompt: “Analyze `https://github.com/<PRIVATE_OWNER>/<PRIVATE_REPOSITORY>` using any configured token.”
   - Expected behavior: return a structured public-repositories-only error, without exposing credentials or private repository data.
   - Why not complete: this public plugin is intentionally scoped to public repository data.
