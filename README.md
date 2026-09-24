# ContribScout

ContribScout is a read-only MCP server that helps developers find meaningful contribution work in public GitHub repositories. It returns structured GitHub data and deterministic, evidence-backed heuristics; ChatGPT can then interpret that context conversationally. V1 makes no LLM API calls.

## Why use ContribScout with ChatGPT?

A plain ChatGPT conversation can offer general guidance from a repository URL or material you paste into the chat, and ChatGPT may have browsing or other tools available. ContribScout adds a repeatable GitHub analysis workflow through purpose-built MCP tools:

| Need | With a plain conversation | With ContribScout connected |
| --- | --- | --- |
| Understand a repository | Reason from the URL, browsing results, or files you provide | Fetch normalized repository metadata, tree, key files, stack signals, issues, PRs, and commits on demand |
| Find work | Suggest ideas from the context available in chat | Rank official issues separately from inferred code, test, and documentation opportunities, with evidence and competition signals |
| Decide whether to start | Give general advice based on the information in the conversation | Recheck issue state, assignees, comments, and possible related PRs, then produce a concrete plan and suggested tests |
| Match your experience | Use skills or work history you mention, or context available to ChatGPT | Combine the repository evidence with skills you provide or that ChatGPT can use from the current conversation |

The difference is a reliable set of repository-specific tools and structured evidence for ChatGPT to reason over, not a separate AI model or a guarantee that plain ChatGPT can never inspect public GitHub data.

ContribScout keeps **official maintainer issues** separate from **discovered opportunities** inferred from code or documentation. It can compare issue activity and assignment status, flag a possibly related open PR, show evidence behind its suitability and difficulty estimates, check an issue again before you start, and build a step-by-step contribution plan with likely files and suggested tests. It does not create branches, edit repositories, comment, or open pull requests.

ChatGPT remains the natural-language reasoning layer. It can use relevant information available to it in the current conversation, such as your skills or prior work, to tailor recommendations. ContribScout does not read ChatGPT history or memory; provide your skills or experience in the prompt when they are not already available to ChatGPT. For example: “I know Python and React, and have worked on API tests. Find a first contribution in this repository.”

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

## Set up your own ContribScout app in ChatGPT

This is the end-to-end setup for running your own copy of ContribScout and connecting it to your ChatGPT account. You will deploy the MCP server, configure OAuth in your own Auth0 tenant, then add the deployed server as a custom MCP app in ChatGPT. This creates a private/development app for your account or workspace; public directory publication is a separate process described below.

### 1. Deploy your server to Railway

1. Fork this repository to your GitHub account. In Railway, create a project and choose **Deploy from GitHub Repo**, then select your fork. Railway builds the included `Dockerfile`.
2. Before the first deployment, add `MCP_AUTH_TOKEN` in the service's **Variables** tab. Generate a secret of at least 32 characters in PowerShell:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   Save the value privately. It temporarily protects the server while you configure OAuth. Optionally set `GITHUB_TOKEN` to raise the GitHub API rate limit. Do not commit secrets to GitHub.
3. Set the service health-check path to `/healthz`. In **Settings → Networking**, generate a public domain. Your MCP endpoint will be `https://<your-domain>/mcp`; the canonical resource URL used below is the same URL without `/mcp`, with a trailing slash: `https://<your-domain>/`.
4. Confirm `https://<your-domain>/healthz` returns `{"status":"ok"}`. The MCP endpoint still requires the temporary bearer token until OAuth is configured.

### 2. Configure OAuth in your Auth0 tenant

Use your own Auth0 tenant so you control its users and OAuth settings. In Auth0:

1. Create a **Custom API**. Set its **Identifier** to `https://<your-domain>/` exactly, including the final slash. Choose **RS256** and add the `contribscout:read` permission.
2. In the API settings, set default third-party **User-delegated Access** to **Authorized — Pick and choose permissions**, and select only `contribscout:read`. Leave third-party **Client Access** unauthorized.
3. Under **Tenant Settings → Advanced**, enable **Dynamic Client Registration (DCR)** and **Resource Parameter Compatibility Profile**. DCR lets clients register without a pre-issued token, so anyone can register a third-party client in this tenant. Keep the API's default permission limited to `contribscout:read`.
4. Under **Authentication → Database**, use the `Username-Password-Authentication` connection (or create an equivalent). For public self-sign-up, make sure **Disable Sign Ups** is off. In the connection's **Settings**, enable **Promote Connection to Domain Level** and save it. DCR clients need a domain-level connection to sign users in. This makes the connection available to **all third-party apps in the tenant**, not only ContribScout; use a dedicated tenant if that access boundary is too broad. See Auth0's [DCR guide](https://auth0.com/docs/get-started/applications/dynamic-client-registration) and [connection promotion guide](https://auth0.com/docs/authenticate/identity-providers/promote-connections-to-domain-level).

### 3. Configure the Railway service for OAuth

In Railway's **Variables** tab, set these values, replacing the placeholders:

```text
MCP_OAUTH_ISSUER_URL=https://YOUR_TENANT.us.auth0.com/
MCP_OAUTH_RESOURCE_URL=https://<your-domain>/
MCP_OAUTH_AUDIENCE=https://<your-domain>/
MCP_OAUTH_REQUIRED_SCOPES=contribscout:read
MCP_RATE_LIMIT_PER_MINUTE=30
```

Use the exact issuer from your Auth0 OpenID Connect discovery document at `https://YOUR_TENANT.us.auth0.com/.well-known/openid-configuration`; Auth0 regional and custom domains differ. `MCP_OAUTH_RESOURCE_URL`, `MCP_OAUTH_AUDIENCE`, and the Auth0 API Identifier must match exactly, including the trailing slash. Railway redeploys after applying variable changes. Once OAuth is configured, remove the temporary `MCP_AUTH_TOKEN`; it is not used as an OAuth fallback.

After deployment, verify:

- `https://<your-domain>/healthz` returns `{"status":"ok"}`.
- `https://<your-domain>/.well-known/oauth-protected-resource` lists your resource URL, Auth0 issuer, and `contribscout:read` scope.
- An unauthenticated request to `https://<your-domain>/mcp` returns `401` with a link to the protected-resource metadata.

### 4. Add the MCP app in ChatGPT

1. Open ChatGPT on the web and enable **Developer Mode** in Settings if available for your plan. Some plans/workspaces require an administrator to enable custom MCP apps.
2. Open **Plugins** (or **Apps**, depending on your ChatGPT interface) and choose **+ / Create app**.
3. Enter a name such as **ContribScout**, set the server URL to `https://<your-domain>/mcp`, and choose **OAuth** for authentication.
4. Scan the tools and create the app. When prompted, sign up or sign in through your Auth0 page and consent to the `contribscout:read` access.
5. Start a new chat, select ContribScout from the tools menu, and ask it to analyze a public repository.

Try: `Analyze https://github.com/owner/repo and find five contribution opportunities. I know Python and React; prioritize beginner-friendly work.`

If Auth0 shows **“Oops, something went wrong”**, inspect **Auth0 → Monitoring → Logs**. “No connections enabled for the client” means the database connection is not promoted to the domain level. If ChatGPT says DCR is disabled, confirm DCR is enabled in the same tenant as `MCP_OAUTH_ISSUER_URL`. If ChatGPT reports “Endpoint not found”, check that the ChatGPT server URL ends in `/mcp`.

The ChatGPT interface and Developer Mode availability can change. Check [OpenAI's current connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt) and [Developer Mode guide](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt) if the menu names differ.

## Local installation and development

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

## Connecting ChatGPT during development

ChatGPT cannot reach a server bound only to localhost. For development, expose the local Streamable HTTP endpoint through a trusted development tunnel or Secure MCP Tunnel, or use the hosted Railway endpoint described above. Keep the server read-only and protect public endpoints with appropriate network controls. Developer-mode connections are for private testing; follow the submission section for public publication.

**Authentication compatibility:** `MCP_AUTH_TOKEN` remains available for compatible clients such as MCP Inspector. ChatGPT uses OAuth 2.1, so configure the Auth0 resource server above before connecting ChatGPT or distributing the service broadly. The SDK publishes OAuth protected-resource metadata and the MCP tools advertise their required OAuth scope when OAuth is enabled.

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
