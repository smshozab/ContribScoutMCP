import re

SKIP_PARTS = {".git", "node_modules", "dist", "build", "vendor", "coverage", "__pycache__", ".venv"}
SKIP_SUFFIXES = {".lock", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".pdf", ".zip", ".woff", ".woff2", ".map", ".min.js", ".min.css", ".csv", ".parquet"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".php", ".c", ".h", ".cpp", ".cs", ".sh", ".yaml", ".yml", ".toml", ".md"}
MARKER = re.compile(r"\b(TODO|FIXME|HACK|XXX|NotImplemented(?:Error)?)\b", re.IGNORECASE)


async def scan_markers(client, owner: str, repo: str, paths: list[str], max_files: int, max_size: int) -> list[dict]:
    candidates = [p for p in paths if not any(part in SKIP_PARTS for part in p.split("/")) and not p.lower().endswith(tuple(SKIP_SUFFIXES)) and any(p.lower().endswith(s) for s in SOURCE_SUFFIXES)][:max_files]
    results = []
    import asyncio
    sem = asyncio.Semaphore(8)
    async def read(path):
        async with sem:
            try:
                return path, await client.file(owner, repo, path)
            except Exception:
                return path, None
    for path, content in await asyncio.gather(*(read(p) for p in candidates)):
        if content is None or len(content.encode("utf-8")) > max_size:
            continue
        for number, line in enumerate(content.splitlines(), 1):
            match = MARKER.search(line)
            if match:
                results.append({"file": path, "line": number, "marker": match.group(1), "context": line.strip()[:300]})
    return results[:500]


def discover_gaps(paths: list[str], markers: list[dict], analysis: dict, commits: list[dict] | None = None) -> list[dict]:
    gaps = [{"type": "DISCOVERED_OPPORTUNITY", "identifier": f"marker:{m['file']}:{m['line']}", "category": "todo", "title": f"Address {m['marker']} in {m['file']}", "evidence": [f"{m['file']}:{m['line']} contains {m['marker']}: {m['context']}"], "confidence": "medium", "recommended_action": "Inspect the marker in context and determine whether a focused fix or follow-up issue is appropriate.", "likely_files": [m["file"]]} for m in markers]
    sources = [p for p in paths if p.startswith(("src/", "lib/", "app/")) and p.lower().endswith((".py", ".js", ".ts", ".go", ".rs", ".java"))]
    tests = [p for p in paths if any(x in p.lower() for x in ("test", "spec"))]
    if sources and not tests:
        gaps.append({"type": "DISCOVERED_OPPORTUNITY", "identifier": "test-gap:no-tests", "category": "testing", "title": "Add an initial automated test suite", "evidence": [f"Found {len(sources)} source files under common source directories.", "No paths containing test or spec were found in the repository tree."], "confidence": "medium", "recommended_action": "Identify a core behavior and add focused tests using the project's existing tooling, if any.", "likely_files": ["tests/ (proposed new directory)"]})
    else:
        modules = [p for p in sources if not any(x in p.lower() for x in ("test", "spec"))]
        unpaired = [p for p in modules if not any(p.rsplit("/", 1)[-1].split(".")[0] in t for t in tests)]
        if len(unpaired) >= 3:
            gaps.append({"type": "DISCOVERED_OPPORTUNITY", "identifier": "test-gap:unpaired-modules", "category": "testing", "title": "Review source modules without obvious test counterparts", "evidence": [f"{len(unpaired)} source modules have no test/spec filename with a matching module stem."], "confidence": "low", "recommended_action": "Review module behavior and add tests for the highest-risk uncovered areas; this heuristic does not measure coverage.", "likely_files": unpaired[:8]})
    readme = analysis.get("readme", "").lower()
    if not analysis.get("readme_present"):
        gaps.append({"type": "DISCOVERED_OPPORTUNITY", "identifier": "docs:no-readme", "category": "documentation", "title": "Add a project README", "evidence": ["No root README.md, README.rst, or README was found."], "confidence": "high", "recommended_action": "Document the project's purpose, setup, and a minimal usage path.", "likely_files": ["README.md (proposed new file)"]})
    if not analysis.get("contribution_guidelines_present"):
        gaps.append({"type": "DISCOVERED_OPPORTUNITY", "identifier": "docs:no-contributing", "category": "documentation", "title": "Document contribution setup and review expectations", "evidence": ["No root CONTRIBUTING.md or CONTRIBUTING.rst was found."], "confidence": "medium", "recommended_action": "Add concise setup, test, and pull request guidance for contributors.", "likely_files": ["CONTRIBUTING.md (proposed new file)"]})
    examples = [p for p in paths if p.startswith("examples/")]
    if examples and analysis.get("readme_present") and "example" not in readme and "usage" not in readme:
        gaps.append({"type": "DISCOVERED_OPPORTUNITY", "identifier": "docs:examples-not-linked", "category": "documentation", "title": "Link repository examples from the README", "evidence": [f"Found {len(examples)} paths under examples/.", "README does not mention examples or usage."], "confidence": "low", "recommended_action": "Add a short README link to the most useful existing example.", "likely_files": ["README.md", examples[0]]})
    return gaps
