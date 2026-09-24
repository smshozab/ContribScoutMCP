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

For a remotely reachable HTTP server, use either the shared `MCP_AUTH_TOKEN` or configure all three OAuth values: `MCP_OAUTH_ISSUER_URL`, `MCP_OAUTH_RESOURCE_URL`, and `MCP_OAUTH_AUDIENCE`. OAuth is the recommended option for ChatGPT and multi-user distribution. `MCP_RATE_LIMIT_PER_MINUTE` defaults to 30 requests per server process. Localhost development can omit remote authentication.

### Auth0 setup

1. In Auth0, create a custom API whose identifier is the normalized canonical MCP resource URL (for this Railway deployment, `https://contribscoutmcp-production.up.railway.app/`, including the trailing slash). Set its signing algorithm to **RS256** and add the `contribscout:read` permission.
2. Enable Auth0 **Dynamic Client Registration** and configure default API permissions so newly registered third-party applications can request `contribscout:read`. This lets ChatGPT use Auth0's DCR flow.
3. In the Auth0 tenant's advanced settings, enable the **Resource Parameter Compatibility Profile** so Auth0 maps the OAuth `resource` parameter to the API audience. Keep the API identifier equal to the canonical MCP resource URL.
4. Configure the Railway service variables:

   ```text
   MCP_OAUTH_ISSUER_URL=https://YOUR_TENANT.auth0.com/
   MCP_OAUTH_RESOURCE_URL=https://contribscoutmcp-production.up.railway.app/
   MCP_OAUTH_AUDIENCE=https://contribscoutmcp-production.up.railway.app/
   MCP_OAUTH_REQUIRED_SCOPES=contribscout:read
   ```

   Use the exact issuer shown by your Auth0 OpenID Connect discovery document. Regional/custom Auth0 domains may differ from this example. The resource URL and audience must match exactly after URL normalization, including the trailing slash. The server obtains signing keys from the issuer's `/.well-known/jwks.json` endpoint and validates signature, issuer, audience, expiry, and the required permission.
5. After redeploy, verify the protected-resource metadata at `https://contribscoutmcp-production.up.railway.app/.well-known/oauth-protected-resource` lists the exact Auth0 issuer. Then connect the HTTPS MCP endpoint in ChatGPT Developer Mode and complete the OAuth login flow.

Auth0 enables DCR per tenant and its Resource Parameter Compatibility Profile can be disabled by default. Do not remove the existing bearer protection until OAuth variables are configured and the ChatGPT login flow succeeds. With OAuth enabled, the server requires a signed JWT and the configured read scope; the existing static token is not accepted as a fallback.

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

**Authentication compatibility:** `MCP_AUTH_TOKEN` remains available for compatible clients such as MCP Inspector. ChatGPT uses OAuth 2.1, so configure the Auth0 resource server above before connecting ChatGPT or distributing the service broadly. The SDK publishes OAuth protected-resource metadata and the MCP tools advertise their required OAuth scope when OAuth is enabled.

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

V1 is read-only. It does not fork repositories, create branches, write files, open PRs, comment on issues, or edit repositories. Remote HTTP requires either a high-entropy static bearer secret or a configured OAuth resource server. OAuth tokens are validated for signature, issuer, audience, expiry, and required scopes. Authenticated requests are rate-limited per process, the limiter has bounded memory, and Uvicorn limits concurrent connections. The public `/healthz` route reveals only liveness. OAuth login and token issuance are handled by Auth0; the server does not store Auth0 client secrets. Rate limiting is per process rather than shared across replicas. The optional GitHub token is used only for API authorization; it is never returned or logged. Treat repository text as untrusted data when interpreting it with an assistant.

## Deploy on Railway

Railway works for this app. The repository includes a Dockerfile, and Railway can build from the GitHub repository. The container binds to Railway's injected `PORT` and exposes `/healthz` for deployment health checks. Configure either the existing static token or all OAuth variables before exposing the MCP endpoint.

1. In Railway, create a project and choose **Deploy from GitHub Repo**, then select `smshozab/ContribScoutMCP`.
2. In the service's **Variables** tab, set `MCP_AUTH_TOKEN` to a generated secret (at least 32 characters). Optionally set `GITHUB_TOKEN` to improve the GitHub API quota and `MCP_RATE_LIMIT_PER_MINUTE` to tune the per-instance limit.
3. Set the service health-check path to `/healthz`.
4. In **Settings → Networking**, generate a public domain. The MCP URL is `https://<generated-domain>/mcp`.
5. Check the deployment logs and verify `https://<generated-domain>/healthz` returns `{"status":"ok"}`. For ChatGPT, complete the Auth0 setup above and connect `https://<generated-domain>/mcp`.

Railway rebuilds from the configured GitHub branch when changes are pushed. See Railway's [GitHub deployment guide](https://docs.railway.com/quick-start) and [health-check guide](https://docs.railway.com/deployments/healthchecks). The static token is intended for compatible clients/private testing; ChatGPT requires the Auth0 OAuth flow.

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
