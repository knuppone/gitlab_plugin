from __future__ import annotations

import json

from typer.testing import CliRunner

from gitlab_mr.cli import app

runner = CliRunner()


def test_pr_dry_run_matches_create() -> None:
    args = [
        "--dry-run",
        "--compact",
        "--project",
        "acme/widget",
        "--source-branch",
        "feat/foo",
        "--target-branch",
        "main",
        "--title",
        "Add foo",
        "--description",
        "body",
    ]
    create_result = runner.invoke(app, ["create", *args])
    pr_result = runner.invoke(app, ["pr", *args])
    assert create_result.exit_code == 0
    assert pr_result.exit_code == 0
    assert json.loads(create_result.stdout) == json.loads(pr_result.stdout)
    payload = json.loads(create_result.stdout)
    assert payload["operation"] == "create_mr"
    assert payload["project"] == "acme/widget"
