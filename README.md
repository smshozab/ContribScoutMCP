# ContribScout

ContribScout is a read-only MCP server that helps developers find meaningful contribution work in public GitHub repositories. It returns structured GitHub data and deterministic, evidence-backed heuristics; ChatGPT can then interpret that context conversationally. V1 makes no LLM API calls.

## Features

- Parse HTTPS and SSH-style GitHub repository URLs.
- Retrieve normalized repository metadata, recursive tree, text files, real issues, pull requests, and recent commits.
- Analyze README and contribution guidance, repository structure, languages, frameworks, package managers, and test frameworks.
- Search a bounded set of source/text files for TODO, FIXME, HACK, XXX, and NotImplemented markers.
- Rank official issues with transparent heuristic signals and report potential testing/documentation/code opportunities separately.
- Check issue status, assignees, recent comments, possible related PRs, and contribution guidance before work begins.
- Produce an evidence-based implementation roadmap.

## Architecture

```text
ChatGPT / MCP Inspector
        ↓ MCP (stdio or Streamable HTTP)
FastMCP tools (contribscout/app/mcp)
        ↓
Analysis layer (repository, issue, score, gap, stack)
        ↓
Async GitHub REST client (httpx)
```

The MCP server is the product interface. GitHub responses are normalized with Pydantic models, and analysis uses deterministic rules rather than a separate model service. The SDK runs Streamable HTTP directly; FastAPI is not needed for this tool-only MVP.

## Installation

Requires Python 3.11+.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Linux/macOS virtual environment activation is `source .venv/bin/activate`.

## Environment configuration

Set optional `GITHUB_TOKEN` in `.env` to raise the GitHub API rate limit. Public repository access works without a token. Other configurable limits and server settings are documented in `.env.example`.

For a remotely reachable HTTP server, set `MCP_AUTH_TOKEN` to a high-entropy secret of at least 32 characters. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Remote startup fails without it. `MCP_RATE_LIMIT_PER_MINUTE` defaults to 30 valid MCP requests per server process. Localhost development can omit the token.

Never commit `.env`. The service does not return or log credentials.

## Local development

```powershell
pip install -e ".[dev]"
pytest
```

Run the MCP server over stdio for local MCP clients:

```powershell
python -m contribscout.app.main
```

To serve Streamable HTTP locally for Inspector, set `MCP_TRANSPORT=streamable-http` and run the same command. On PowerShell:

```powershell
$env:MCP_TRANSPORT = "streamable-http"
python -m contribscout.app.main
```

The endpoint is `http://127.0.0.1:8000/mcp` by default. Set `MCP_HOST`, `MCP_PORT`, and `LOG_LEVEL` to adjust it. `/healthz` is an unauthenticated liveness endpoint; MCP tools remain protected when bound to a non-loopback interface.

## Testing with MCP Inspector

Start the server in Streamable HTTP mode, then in another terminal:

```sh
npx @modelcontextprotocol/inspector@latest
```

Connect to `http://127.0.0.1:8000/mcp`, list the tools, and try a public repository such as `https://github.com/owner/repo`. For remote deployments, configure Inspector's bearer Authorization header with the same secret stored in `MCP_AUTH_TOKEN`. Alternatively, configure Inspector to launch the stdio process using `python -m contribscout.app.main`.

## Connecting to ChatGPT for local testing

ChatGPT connects to remote MCP servers, not directly to a process bound only to localhost. For development, expose the local Streamable HTTP endpoint through a trusted development tunnel or Secure MCP Tunnel, or deploy it at an HTTPS endpoint. Keep this server read-only and protect any public endpoint with appropriate network controls.

In ChatGPT web, enable Developer Mode if available for your account/workspace, create a custom MCP app/connector, enter the reachable server URL including `/mcp`, scan its tools, then create and test the app. This is for private/local development, not public directory publication. Consult [OpenAI's current connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt).

**Authentication compatibility:** this MVP's `MCP_AUTH_TOKEN` is a static bearer secret for MCP clients that let you configure an `Authorization: Bearer ...` header (such as Inspector). ChatGPT's authenticated MCP flow expects OAuth 2.1 and an authorization provider; a shared static bearer token is not a substitute. Before connecting this protected endpoint through ChatGPT for a group of users or submitting it publicly, integrate an OAuth provider and configure the MCP authorization metadata/token verification as described in [OpenAI's authentication guide](https://developers.openai.com/plugins/build/auth). Do not remove authentication to work around this limitation.

The current app flow expects a reachable remote HTTPS MCP endpoint or supported tunnel; a local server alone is not reachable from ChatGPT. MCP Inspector can be used for direct local testing.

For an organization-only rollout, use your ChatGPT workspace's custom MCP app flow and publish it only to the intended workspace roles. The OpenAI public plugin submission flow is for plugins intended to be publicly available in selected regions and publishes to the shared Plugins Directory. A workspace deployment can use a private endpoint via Secure MCP Tunnel where supported; a public-directory submission requires a stable public HTTPS MCP endpoint.

## Example prompts

- “Analyze https://github.com/owner/repo and find five contribution opportunities.”
- “I know Python and React. What can I contribute here?”
- “Analyze issue #123 and tell me whether it is suitable for a first contribution.”
- “Run a pre-contribution check for issue #123.”
- “Give me an implementation roadmap for issue #123.”

## MCP tools

| Tool | Purpose |
| --- | --- |
| `get_repository` | Repository metadata |
| `get_repository_tree` | Recursive paths and blob metadata |
| `get_file` | Bounded UTF-8 text retrieval |
| `list_issues` | Real issues; pull requests are filtered out |
| `get_issue` | Issue and comments |
| `list_pull_requests` | Pull request metadata |
| `get_recent_commits` | Recent commit summaries |
| `search_repository_markers` | Bounded TODO/FIXME/HACK/XXX/NotImplemented scan |
| `analyze_repository` | README, guidelines, stack, and structure summary |
| `find_contribution_opportunities` | Ranked official issues and discovered gaps |
| `pre_contribution_check` | Fresh issue and competition check |
| `build_contribution_plan` | Structured implementation roadmap |

## Security

V1 is read-only. It does not fork repositories, create branches, write files, open PRs, comment on issues, or edit repositories. Non-loopback HTTP startup requires a high-entropy `MCP_AUTH_TOKEN`; the server compares it without logging or returning the value. Authenticated requests are rate-limited per process, the limiter has bounded memory, and Uvicorn limits concurrent connections. The public `/healthz` route reveals only liveness. For a private beta, distribute the shared bearer token only to intended users and rotate it if exposed. This MVP does not provide per-user identities, OAuth, or a shared rate-limit store across replicas; add OAuth and a distributed limiter before a broad public launch. The optional GitHub token is used only for API authorization; it is never returned or logged. Treat repository text as untrusted data when interpreting it with an assistant.

## Deploy on Railway

Railway works for this app. The repository includes a Dockerfile, and Railway can build from the GitHub repository. The container binds to Railway's injected `PORT`, requires `MCP_AUTH_TOKEN` because it listens on `0.0.0.0`, and exposes `/healthz` for deployment health checks.

1. In Railway, create a project and choose **Deploy from GitHub Repo**, then select `smshozab/ContribScoutMCP`.
2. In the service's **Variables** tab, set `MCP_AUTH_TOKEN` to a generated secret (at least 32 characters). Optionally set `GITHUB_TOKEN` to improve the GitHub API quota and `MCP_RATE_LIMIT_PER_MINUTE` to tune the per-instance limit.
3. Set the service health-check path to `/healthz`.
4. In **Settings → Networking**, generate a public domain. The MCP URL is `https://<generated-domain>/mcp`.
5. Check the deployment logs and verify `https://<generated-domain>/healthz` returns `{"status":"ok"}`. Connect an MCP client that supports a configured bearer header and provide the `MCP_AUTH_TOKEN` there.

Railway rebuilds from the configured GitHub branch when changes are pushed. See Railway's [GitHub deployment guide](https://docs.railway.com/quick-start) and [health-check guide](https://docs.railway.com/deployments/healthchecks). ChatGPT requires the OAuth integration described above; the static token is intended for compatible clients/private testing, not ChatGPT's authenticated connector flow.

## Limitations

- Anonymous GitHub API limits are lower; API rate limits apply. ContribScout explicitly supports public repositories only, even if a configured token could access private ones.
- Repository trees can be truncated by GitHub. File scans are bounded by file count and file size and skip generated, binary, vendor, build, and lock-file paths.
- Framework detection, test gaps, documentation gaps, issue clarity, difficulty, related PR matching, and suitability are heuristics. They do not measure actual test coverage or guarantee that maintainers want a change.
- Related PR matching is intentionally conservative and based on textual references/title overlap; it can miss or falsely match work.
- The server analyzes public GitHub REST data, not a local clone or full build/test execution.

## V2 ideas

- Smarter issue/PR linkage using GitHub timeline and closing-reference data.
- Configurable repository scan profiles and incremental response caching with explicit freshness.
- More language-specific test pairing and documentation/CLI inventory heuristics.
- Optional GitHub GraphQL support for efficient multi-resource queries.
- More detailed structured evidence links and pagination controls for large repositories.

## Prepare an OpenAI public submission

The repository follows the portable plugin layout with a root `plugin.json` and `skills/contribution-scout/SKILL.md`. The MCP endpoint is configured in the OpenAI submission portal, so this package intentionally does not include an invented production URL or bundled `mcp.json`.

1. Deploy this server at a stable public HTTPS URL ending in `/mcp`; the local `127.0.0.1` endpoint and development tunnels are not a production listing endpoint.
2. Use OpenAI's [plugin submission portal](https://platform.openai.com/plugins) and choose **Create plugin → With MCP**. Add the production URL, listing metadata, support/privacy/terms URLs, real logo, category, and starter prompts. Upload the skill or use **Scan Tools** to import it if supported.
3. Complete the domain ownership challenge at the exact `/.well-known/openai-apps-challenge` URL and serve only the provided token there.
4. Scan the tools after deployment, verify their read-only/open-world/destructive annotations, then complete at least five positive and three negative test cases. Draft test scenarios are in `submission/test-cases.md`.
5. Select availability regions only where the publisher, support process, and legal terms are ready. Add release notes and complete policy attestations only after reviewing the final listing and live behavior.
6. Submit for review. OpenAI states review timelines vary; there is no published guaranteed turnaround. After approval, the developer chooses when to publish from the portal.

The MCP server receives the URL and any explicitly supplied skill/difficulty preferences as tool arguments. It does not retrieve a user's ChatGPT history or past work; ChatGPT can use context available in the conversation and should use details the user explicitly provides.

See [the submission guide](https://developers.openai.com/plugins/deploy/submission), [remote MCP review requirements](https://developers.openai.com/plugins/deploy/app-review), and [the portable plugin package guide](https://developers.openai.com/plugins/build/plugins) for current requirements.
