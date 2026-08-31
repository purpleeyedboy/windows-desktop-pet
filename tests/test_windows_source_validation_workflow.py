from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "windows-source-validation.yml"
)


def test_windows_source_validation_workflow_is_security_constrained():
    assert WORKFLOW.is_file(), "Windows source-validation workflow is missing"

    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "on:\n"
        "  pull_request:\n"
        "    branches:\n"
        "      - codex/desktop-pet-6-frame-alpha\n"
        "  workflow_dispatch:\n\n"
        "permissions:\n"
        "  contents: read\n\n"
        "jobs:\n" in workflow
    )
    assert "windows-source-tests:" in workflow
    assert "runs-on: windows-latest" in workflow
    assert "python-version: \"3.11\"" in workflow
    assert "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0" in workflow
    assert "persist-credentials: false" in workflow
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
    assert workflow.count("uses: ") == 2
    assert "python -m pip install \".[dev]\"" in workflow
    assert "PIL.__version__.split(\".\", 1)[0] == \"11\"" in workflow
    assert "python -m pytest -q" in workflow
    assert "secrets." not in workflow.lower()
    assert "upload-artifact" not in workflow.lower()
    assert "pyinstaller" not in workflow.lower()
