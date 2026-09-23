from collections import Counter

MANIFESTS = {"package.json": ("JavaScript/TypeScript", "npm"), "pyproject.toml": ("Python", "pip/poetry/uv"), "requirements.txt": ("Python", "pip"), "Pipfile": ("Python", "pipenv"), "Cargo.toml": ("Rust", "cargo"), "go.mod": ("Go", "go modules"), "pom.xml": ("Java", "Maven"), "build.gradle": ("Java", "Gradle"), "Gemfile": ("Ruby", "Bundler"), "composer.json": ("PHP", "Composer")}
TEST_HINTS = {"pytest": ("pytest", "pytest"), "unittest": ("Python", "unittest"), "jest": ("JavaScript/TypeScript", "Jest"), "vitest": ("JavaScript/TypeScript", "Vitest"), "mocha": ("JavaScript/TypeScript", "Mocha"), "testing": ("Go", "Go testing")}


def detect_stack(paths: list[str], primary_language: str | None = None, manifest_texts: dict[str, str] | None = None) -> dict:
    manifests = {p.rsplit("/", 1)[-1] for p in paths}
    languages = {lang for name, (lang, _) in MANIFESTS.items() if name in manifests}
    if primary_language:
        languages.add(primary_language)
    managers = sorted({manager for name, (_, manager) in MANIFESTS.items() if name in manifests})
    texts = "\n".join((manifest_texts or {}).values()).lower()
    tests = sorted({framework for key, (_, framework) in TEST_HINTS.items() if key in texts})
    frameworks = []
    for marker, framework in [("fastapi", "FastAPI"), ("django", "Django"), ("flask", "Flask"), ("react", "React"), ("next", "Next.js"), ("vue", "Vue"), ("express", "Express"), ("pytest", "pytest")]:
        if marker in texts and framework not in frameworks:
            frameworks.append(framework)
    return {"languages": sorted(languages), "frameworks": frameworks, "package_managers": managers, "test_frameworks": tests}
