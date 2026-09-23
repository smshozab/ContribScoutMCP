# OpenAI listing draft

Fill the marked fields with real publisher and legal/support information before submission. Do not publish with example values or a development endpoint.

- **Name:** ContribScout
- **Category:** Developer tools (choose the closest category offered by the portal)
- **Short description:** Find evidence-backed ways to contribute to public GitHub projects.
- **Long description:** ContribScout analyzes public repository metadata, documentation, structure, issues, pull requests, commits, and bounded code markers. It separates official GitHub issues from heuristic opportunities, explains its evidence and uncertainty, and creates a practical contribution roadmap. It is read-only and does not create branches, comments, or pull requests.
- **Starter prompts:**
  - Analyze a public GitHub repository and recommend contribution opportunities.
  - I know Python and React. Which opportunities fit my experience?
  - Check whether this open issue is a reasonable first contribution and plan the work.
- **Website:** [publisher must supply a real public product/project page]
- **Support URL/email:** [publisher must supply a monitored contact]
- **Privacy policy URL:** [publisher must publish an accurate policy]
- **Terms URL:** [publisher must publish applicable terms]
- **Publisher identity:** [verified developer or business identity with Apps Management write access]
- **Production MCP URL:** [stable public HTTPS host ending in `/mcp`]
- **Logo:** [publisher must provide a real listing logo]
- **Release note:** Initial release. Read-only MCP tools retrieve public GitHub repository data and return deterministic contribution discovery and planning guidance. No user GitHub write actions are supported.

## Data and personalization statement for the listing

The server receives explicit MCP tool inputs such as a repository URL and optional skills/preferences, and requests public GitHub data. It does not connect to or retrieve a user's ChatGPT chat history, saved memories, or past work. ChatGPT may use information the user supplies in the current conversation when choosing and explaining recommendations. Do not claim otherwise in listing copy.
