from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any, Optional, Tuple

import httpx
import typer

from gitlab_mr.client import GitLabMrClient, dump_json_stdout, normalize_discussions
from gitlab_mr.parsing import MrReference, normalize_project_segment, parse_merge_request_identifier

__version__: str = "0.1.0"


def _maybe_print_version(do_print: bool) -> bool:
    if do_print:
        typer.echo(__version__)
        raise typer.Exit()
    return do_print


app = typer.Typer(
    no_args_is_help=True,
    context_settings=dict(help_option_names=["--help", "-h"]),
    help="GitLab merge request discussions, comments, replies, and creation.",
)


@app.callback()
def _root_flags(
    _: bool = typer.Option(False, "--version", "-V", is_flag=True, is_eager=True, callback=_maybe_print_version),
) -> None:
    """Authenticate with GITLAB_TOKEN; override base URL via GITLAB_URL or --gitlab-url."""


def _gitlab_base(cli_value: Optional[str]) -> str:
    trimmed_cli = (cli_value or "").strip()
    if trimmed_cli:
        return trimmed_cli.rstrip("/")
    env_value = os.environ.get("GITLAB_URL", "").strip()
    return env_value.rstrip("/") if env_value else "https://gitlab.com"


def _token(cli_override: Optional[str]) -> str:
    if cli_override is not None and cli_override.strip():
        return cli_override.strip()
    return os.environ.get("GITLAB_TOKEN", "").strip()


def _require_live_token(secret: str) -> str:
    if secret.strip():
        return secret.strip()
    typer.echo("Missing GITLAB_TOKEN (export it or pass --token).", err=True)
    raise typer.Exit(code=1)


def _emit(obj: Any, *, compact_json: bool) -> None:
    dumped = dump_json_stdout(obj)
    if compact_json:
        typer.echo(json.dumps(json.loads(dumped), ensure_ascii=False, separators=(",", ":")))
    else:
        typer.echo(dumped)


def _http_error(exc: BaseException, verbose: bool) -> None:
    if isinstance(exc, httpx.HTTPStatusError):
        typer.echo(f"GitLab HTTP {exc.response.status_code}", err=True)
        body = exc.response.text
        typer.echo(body if len(body) <= 4096 else f"{body[:4096]}…", err=True)
    else:
        typer.echo(str(exc), err=True)
    if verbose:
        typer.echo(repr(exc), err=True)


def _read_file(path_: pathlib.Path) -> str:
    return path_.expanduser().resolve(strict=True).read_text(encoding="utf-8")


def _mr_ref(merge_indicator: str, project_cli: Optional[str]) -> MrReference:
    project_segment = normalize_project_segment(project_cli.strip()) if project_cli else None
    return parse_merge_request_identifier(merge_indicator, project_segment if project_segment else None)


def _markdown_body(
    body: Optional[str],
    body_file: Optional[pathlib.Path],
    *,
    command_label: str,
) -> str:
    if body_file is not None and body is not None:
        typer.echo("Use either --body or --body-file, not both.", err=True)
        raise typer.Exit(code=1)

    markdown_payload: str

    if body_file is not None:
        markdown_payload = _read_file(body_file).strip("\n")
    elif body is None:
        markdown_payload = sys.stdin.read().strip("\n")
    elif body.strip() == "-":
        stream = sys.stdin.read()
        if stream.strip() == "":
            typer.echo("stdin for body was empty.", err=True)
            raise typer.Exit(code=1)
        markdown_payload = stream.strip("\n")
    else:
        markdown_payload = body.strip("\n")

    if markdown_payload.strip() == "":
        typer.echo(
            f"{command_label} needs non-empty markdown (--body, --body-file, or stdin).",
            err=True,
        )
        raise typer.Exit(code=1)
    return markdown_payload


def _post_mr_markdown_run(
    *,
    merge_indicator: str,
    project_cli: Optional[str],
    gitlab_url: Optional[str],
    token_cli: Optional[str],
    timeout: float,
    verbose: bool,
    compact_json: bool,
    dry_run: bool,
    operation: str,
    markdown: str,
    discussion_id: Optional[str] = None,
) -> None:
    ref = _mr_ref(merge_indicator, project_cli)
    base = _gitlab_base(gitlab_url)
    if dry_run:
        payload: dict[str, Any] = dict(
            operation=operation,
            base_url=base,
            project=str(ref.project),
            merge_request_iid=ref.iid,
            markdown_chars=len(markdown),
            token_present=len(_token(token_cli)) > 0,
        )
        if discussion_id is not None:
            payload["discussion_id"] = discussion_id
        _emit(payload, compact_json=compact_json)
        return
    secret = _require_live_token(_token(token_cli))
    try:
        with GitLabMrClient(base_url=base, token=secret, timeout_seconds=float(timeout)) as client:
            if discussion_id is not None:
                created = dict(
                    client.reply_to_discussion(
                        project=ref.project,
                        mr_iid=ref.iid,
                        discussion_id=discussion_id,
                        body=markdown,
                    )
                )
            else:
                created = dict(
                    client.create_mr_note(
                        project=ref.project,
                        mr_iid=ref.iid,
                        body=markdown,
                    )
                )
        _emit(created, compact_json=compact_json)
    except BaseException as err:
        _http_error(err, verbose)
        raise typer.Exit(code=1) from err


def _description_text(literal: Optional[str], file_path: Optional[pathlib.Path]) -> Tuple[str, str]:
    if file_path is not None and literal is not None:
        typer.echo("Use either --description or --description-file, not both.", err=True)
        raise typer.Exit(code=1)
    if file_path is not None:
        return _read_file(file_path).strip("\n"), "description_file"
    if literal is None:
        if sys.stdin.isatty():
            typer.echo("Provide --description, --description-file, or pipe description on stdin.", err=True)
            raise typer.Exit(code=1)
        payload = sys.stdin.read()
        return payload.strip("\n"), "stdin_pipe"
    if literal.strip() == "-":
        payload = sys.stdin.read()
        if payload.strip() == "":
            typer.echo("stdin for --description - was empty.", err=True)
            raise typer.Exit(code=1)
        return payload.strip("\n"), "stdin_flag"
    return literal.strip("\n"), "description_flag"


def _discussions_run(
    merge_indicator: str,
    project_cli: Optional[str],
    gitlab_url: Optional[str],
    token_cli: Optional[str],
    timeout: float,
    verbose: bool,
    compact_json: bool,
    per_page: int,
    max_pages: Optional[int],
    dry_run: bool,
) -> None:
    ref = _mr_ref(merge_indicator, project_cli)
    base = _gitlab_base(gitlab_url)
    if dry_run:
        _emit(
            dict(
                operation="list_discussions",
                base_url=base,
                project=str(ref.project),
                merge_request_iid=ref.iid,
                per_page=per_page,
                max_pages=max_pages,
                token_present=len(_token(token_cli)) > 0,
            ),
            compact_json=compact_json,
        )
        return
    secret = _require_live_token(_token(token_cli))
    try:
        with GitLabMrClient(base_url=base, token=secret, timeout_seconds=float(timeout)) as client:
            raw = client.list_mr_discussions_paginated(
                project=ref.project,
                mr_iid=ref.iid,
                per_page=max(1, int(per_page)),
                max_pages=max_pages,
            )
        _emit(normalize_discussions(raw), compact_json=compact_json)
    except BaseException as err:
        _http_error(err, verbose)
        raise typer.Exit(code=1) from err


@app.command("discussions")
def discussions_cmd(
    merge_indicator: str = typer.Argument(..., metavar="MR", help="MR URL or IID (IID needs --project)."),
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    gitlab_url: Optional[str] = typer.Option(None, "--gitlab-url", envvar="GITLAB_URL", show_envvar=False),
    token_cli: Optional[str] = typer.Option(None, "--token", envvar="GITLAB_TOKEN", show_envvar=False),
    timeout: float = typer.Option(30.0, "--timeout"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    compact_json: bool = typer.Option(False, "--compact"),
    per_page: int = typer.Option(20, "--per-page", min=1, max=100),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", min=1),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """List normalized MR discussion threads (review comments)."""

    _discussions_run(
        merge_indicator,
        project,
        gitlab_url,
        token_cli,
        timeout,
        verbose,
        compact_json,
        per_page,
        max_pages,
        dry_run,
    )


@app.command("review-comments")
def review_comments_cmd(
    merge_indicator: str = typer.Argument(..., metavar="MR"),
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    gitlab_url: Optional[str] = typer.Option(None, "--gitlab-url", envvar="GITLAB_URL", show_envvar=False),
    token_cli: Optional[str] = typer.Option(None, "--token", envvar="GITLAB_TOKEN", show_envvar=False),
    timeout: float = typer.Option(30.0, "--timeout"),
    verbose: bool = typer.Option(False, "--verbose"),
    compact_json: bool = typer.Option(False, "--compact"),
    per_page: int = typer.Option(20, "--per-page", min=1, max=100),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", min=1),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Alias of `discussions` (GitHub-ish wording)."""

    _discussions_run(
        merge_indicator,
        project,
        gitlab_url,
        token_cli,
        timeout,
        verbose,
        compact_json,
        per_page,
        max_pages,
        dry_run,
    )


@app.command("comment")
def comment_cmd(
    merge_indicator: str = typer.Argument(..., metavar="MR", help="MR URL or IID (IID needs --project)."),
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    body: Optional[str] = typer.Option(
        None,
        "--body",
        "-b",
        help="Top-level MR comment markdown (`-` or omit to read stdin).",
    ),
    body_file: Optional[pathlib.Path] = typer.Option(None, "--body-file", exists=True),
    gitlab_url: Optional[str] = typer.Option(None, "--gitlab-url", envvar="GITLAB_URL", show_envvar=False),
    token_cli: Optional[str] = typer.Option(None, "--token", envvar="GITLAB_TOKEN", show_envvar=False),
    timeout: float = typer.Option(30.0, "--timeout"),
    verbose: bool = typer.Option(False, "--verbose"),
    compact_json: bool = typer.Option(False, "--compact"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Add a top-level merge request comment (GitLab MR note, not a threaded reply)."""

    markdown = _markdown_body(body, body_file, command_label="comment")
    _post_mr_markdown_run(
        merge_indicator=merge_indicator,
        project_cli=project,
        gitlab_url=gitlab_url,
        token_cli=token_cli,
        timeout=timeout,
        verbose=verbose,
        compact_json=compact_json,
        dry_run=dry_run,
        operation="create_mr_note",
        markdown=markdown,
    )


@app.command("note")
def note_cmd(
    merge_indicator: str = typer.Argument(..., metavar="MR"),
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    body: Optional[str] = typer.Option(None, "--body", "-b"),
    body_file: Optional[pathlib.Path] = typer.Option(None, "--body-file", exists=True),
    gitlab_url: Optional[str] = typer.Option(None, "--gitlab-url", envvar="GITLAB_URL", show_envvar=False),
    token_cli: Optional[str] = typer.Option(None, "--token", envvar="GITLAB_TOKEN", show_envvar=False),
    timeout: float = typer.Option(30.0, "--timeout"),
    verbose: bool = typer.Option(False, "--verbose"),
    compact_json: bool = typer.Option(False, "--compact"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Alias of `comment` (GitLab calls these merge request notes)."""

    markdown = _markdown_body(body, body_file, command_label="note")
    _post_mr_markdown_run(
        merge_indicator=merge_indicator,
        project_cli=project,
        gitlab_url=gitlab_url,
        token_cli=token_cli,
        timeout=timeout,
        verbose=verbose,
        compact_json=compact_json,
        dry_run=dry_run,
        operation="create_mr_note",
        markdown=markdown,
    )


@app.command("reply")
def reply_cmd(
    merge_indicator: str = typer.Argument(..., metavar="MR"),
    discussion_id: str = typer.Option(..., "--discussion-id", help="Thread id from `discussions` JSON."),
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    body: Optional[str] = typer.Option(None, "--body", "-b"),
    body_file: Optional[pathlib.Path] = typer.Option(None, "--body-file", exists=True),
    gitlab_url: Optional[str] = typer.Option(None, "--gitlab-url", envvar="GITLAB_URL", show_envvar=False),
    token_cli: Optional[str] = typer.Option(None, "--token", envvar="GITLAB_TOKEN", show_envvar=False),
    timeout: float = typer.Option(30.0, "--timeout"),
    verbose: bool = typer.Option(False, "--verbose"),
    compact_json: bool = typer.Option(False, "--compact"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Post a threaded reply onto an existing MR discussion."""

    markdown = _markdown_body(body, body_file, command_label="reply")
    _post_mr_markdown_run(
        merge_indicator=merge_indicator,
        project_cli=project,
        gitlab_url=gitlab_url,
        token_cli=token_cli,
        timeout=timeout,
        verbose=verbose,
        compact_json=compact_json,
        dry_run=dry_run,
        operation="reply_discussion_note",
        markdown=markdown,
        discussion_id=discussion_id.strip(),
    )


@app.command("create")
def create_cmd(
    project: str = typer.Option(..., "--project", "-p"),
    source_branch: str = typer.Option(..., "--source-branch"),
    target_branch: str = typer.Option(..., "--target-branch"),
    title: str = typer.Option(..., "--title"),
    description: Optional[str] = typer.Option(None, "--description", "-d"),
    description_file: Optional[pathlib.Path] = typer.Option(None, "--description-file", exists=True),
    gitlab_url: Optional[str] = typer.Option(None, "--gitlab-url", envvar="GITLAB_URL", show_envvar=False),
    token_cli: Optional[str] = typer.Option(None, "--token", envvar="GITLAB_TOKEN", show_envvar=False),
    timeout: float = typer.Option(30.0, "--timeout"),
    verbose: bool = typer.Option(False, "--verbose"),
    compact_json: bool = typer.Option(False, "--compact"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Open a merge request."""

    slug = normalize_project_segment(project.strip())
    text, provenance = _description_text(description, description_file)
    base = _gitlab_base(gitlab_url)
    if dry_run:
        _emit(
            dict(
                operation="create_mr",
                base_url=base,
                project=slug,
                source_branch=source_branch,
                target_branch=target_branch,
                title_chars=len(title.strip()),
                description_source=provenance,
                description_chars=len(text),
                token_present=len(_token(token_cli)) > 0,
            ),
            compact_json=compact_json,
        )
        return
    secret = _require_live_token(_token(token_cli))
    try:
        with GitLabMrClient(base_url=base, token=secret, timeout_seconds=float(timeout)) as client:
            mr = dict(
                client.create_merge_request(
                    project=slug,
                    source_branch=source_branch.strip(),
                    target_branch=target_branch.strip(),
                    title=title.strip(),
                    description=text,
                )
            )
        _emit(mr, compact_json=compact_json)
    except BaseException as err:
        _http_error(err, verbose)
        raise typer.Exit(code=1) from err


def main() -> None:
    app()


if __name__ == "__main__":
    main()
