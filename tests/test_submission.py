import json
from pathlib import Path

from contribscout.app.main import mcp

ROOT = Path(__file__).resolve().parents[1]


def test_portable_plugin_manifest_and_skill_are_present():
    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "contribscout"
    assert manifest["$schema"].endswith("plugin.schema.json")
    assert (ROOT / "skills" / "contribution-scout" / "SKILL.md").is_file()


def test_submission_test_plan_has_five_positive_and_three_negative_cases():
    cases = (ROOT / "submission" / "test-cases.md").read_text(encoding="utf-8")
    assert "## Positive cases" in cases and "## Negative cases" in cases
    positive, negative = cases.split("## Negative cases", maxsplit=1)
    assert sum(line[:1].isdigit() and line[1:3] == ". " for line in positive.splitlines()) == 5
    assert sum(line[:1].isdigit() and line[1:3] == ". " for line in negative.splitlines()) == 3


def test_registered_tools_advertise_read_only_public_internet_behavior():
    tools = mcp._tool_manager.list_tools()
    assert len(tools) == 12
    assert "analyze_repository" in {tool.name for tool in tools}
    for tool in tools:
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.openWorldHint is True
        assert tool.annotations.destructiveHint is False
