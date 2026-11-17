"""Integration tests: full pipeline on example files."""

import json
import pytest
from pathlib import Path

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_common_mecs_check():
    from mecsl.pipeline import Pipeline
    pipe = Pipeline(str(EXAMPLES / "common.mecs"))
    result = pipe.run()
    assert not pipe.bag.has_errors
    assert "logging" in result["config"]
    assert "server_defaults" in result["config"]


def test_app_mecs_full_pipeline():
    from mecsl.pipeline import Pipeline
    pipe = Pipeline(str(EXAMPLES / "app.mecs"))
    result = pipe.run()
    assert not pipe.bag.has_errors
    cfg = result["config"]
    assert cfg["application"]["name"] == "College Portal"
    assert cfg["server"]["host"] == "localhost"
    assert cfg["server"]["port"] == 8080


def test_app_mecs_script_exists():
    from mecsl.pipeline import Pipeline
    pipe = Pipeline(str(EXAMPLES / "app.mecs"))
    result = pipe.run()
    assert "start" in result["scripts"]
    cmds = result["scripts"]["start"]
    actions = [c["action"] for c in cmds]
    assert "print" in actions
    assert "dry_run" in actions


def test_invalid_undefined_reference_caught():
    from mecsl.pipeline import Pipeline
    from mecsl.diagnostics import DiagnosticError
    pipe = Pipeline(str(EXAMPLES / "invalid_undefined_reference.mecs"))
    with pytest.raises(DiagnosticError) as exc_info:
        pipe.run()
    codes = [d.code for d in exc_info.value.diagnostics]
    assert "E203" in codes


def test_invalid_macro_arguments_caught():
    from mecsl.pipeline import Pipeline
    from mecsl.diagnostics import DiagnosticError
    pipe = Pipeline(str(EXAMPLES / "invalid_macro_arguments.mecs"))
    with pytest.raises(DiagnosticError) as exc_info:
        pipe.run()
    codes = [d.code for d in exc_info.value.diagnostics]
    assert "E302" in codes


def test_tokens_command(tmp_path):
    """Test the tokens CLI command returns exit 0 on a valid file."""
    from mecsl.cli import cmd_tokens
    import argparse
    args = argparse.Namespace(file=str(EXAMPLES / "common.mecs"))
    rc = cmd_tokens(args)
    assert rc == 0


def test_build_writes_json(tmp_path):
    """Test the build command produces valid JSON."""
    from mecsl.cli import cmd_build
    import argparse
    out = tmp_path / "out.json"
    args = argparse.Namespace(
        file=str(EXAMPLES / "app.mecs"),
        output=str(out),
    )
    rc = cmd_build(args)
    assert rc == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert "application" in data
    assert data["server"]["port"] == 8080


def test_app_logging_from_common():
    """Verify that import resolution brings in logging from common.mecs."""
    from mecsl.pipeline import Pipeline
    pipe = Pipeline(str(EXAMPLES / "app.mecs"))
    result = pipe.run()
    assert "logging" in result["config"]
    assert result["config"]["logging"]["level"] == "info"
