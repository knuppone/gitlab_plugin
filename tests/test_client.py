import json

import httpx

from gitlab_mr.client import GitLabMrClient, build_discussions_envelope, normalize_discussions


def test_normalize_discussions_agent_slim_shape() -> None:
    blob = dict(
        id="discussion-9",
        resolved=False,
        notes=[
            dict(
                id=101,
                body="LGTM",
                author=dict(
                    username="bot",
                    avatar_url="https://gitlab.com/avatar.png",
                    name="Bot",
                ),
                created_at="2020-04-06T07:53:43.120Z",
                noteable_type="MergeRequest",
            ),
        ],
    )
    normalized = normalize_discussions([blob], output_format="agent")
    thread = normalized[0]
    assert thread["discussion_id"] == "discussion-9"
    assert "position" not in thread
    note = thread["notes"][0]
    assert note["author"] == "bot"
    assert note["body"] == "LGTM"
    assert "avatar_url" not in note
    assert "id" not in note


def test_normalize_discussions_agent_inline_position() -> None:
    blob = dict(
        id="d-inline",
        resolved=False,
        position=dict(
            base_sha="b",
            head_sha="h",
            start_sha="s",
            position_type="text",
            new_path="src/a.py",
            old_path="src/a.py",
            new_line=42,
        ),
        notes=[dict(body="nit", author=dict(username="rev"), created_at="2020-01-01T00:00:00Z")],
    )
    normalized = normalize_discussions([blob], output_format="agent")
    pos = normalized[0]["position"]
    assert pos["file"] == "src/a.py"
    assert pos["line"] == 42
    assert "base_sha" not in pos


def test_build_discussions_envelope_includes_source_branch() -> None:
    mr = dict(source_branch="feature/foo", iid=12)
    blob = dict(
        id="discussion-1",
        resolved=False,
        notes=[dict(body="ok", author=dict(username="rev"), created_at="2020-01-01T00:00:00Z")],
    )
    envelope = build_discussions_envelope(mr, [blob], output_format="agent")
    assert envelope["source_branch"] == "feature/foo"
    assert len(envelope["discussions"]) == 1
    assert envelope["discussions"][0]["discussion_id"] == "discussion-1"


def test_build_discussions_envelope_raises_when_source_branch_missing() -> None:
    import pytest

    with pytest.raises(ValueError, match="source_branch"):
        build_discussions_envelope(dict(iid=1), [])


def test_normalize_discussions_full_keeps_verbose_fields() -> None:
    blob = dict(
        id="discussion-9",
        notes=[
            dict(
                id=101,
                body="LGTM",
                author=dict(username="bot"),
                created_at="2020-04-06T07:53:43.120Z",
            ),
        ],
    )
    normalized = normalize_discussions([blob], output_format="full")
    assert normalized[0]["discussion_id"] == "discussion-9"
    assert normalized[0]["notes"][0]["id"] == 101


def test_list_discussions_stops_when_max_pages_reached_before_next_request() -> None:
    invocation_count = dict(n=0)

    def responder(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        invocation_count["n"] += 1
        payload = [{"id": f"discussion-{idx}", "notes": []} for idx in range(30)]
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(responder)
    with GitLabMrClient(base_url="https://gitlab.invalid", token="secret", timeout_seconds=1.0, transport=transport) as client:
        collected = client.list_mr_discussions_paginated(project="demo/app", mr_iid=12, per_page=20, max_pages=1)
        assert invocation_count["n"] == 1
        assert len(collected) == 30


def test_reply_posts_json_document() -> None:
    recorder: dict[str, str] = dict()

    def responder(request: httpx.Request) -> httpx.Response:
        recorder.update(
            dict(
                method=request.method,
                path=request.url.path,
                body=request.content.decode("utf-8"),
            )
        )
        return httpx.Response(201, json=dict(id=9011, note="created"))

    transport = httpx.MockTransport(responder)
    cli = GitLabMrClient(base_url="https://gitlab.invalid", token="token", timeout_seconds=6.0, transport=transport)
    try:
        out = cli.reply_to_discussion(project="grp/proj", mr_iid=4, discussion_id="d1", body="thanks")
        assert out["note"] == "created"
        assert recorder["method"] == "POST"
        assert json.loads(recorder["body"]) == dict(body="thanks")
        assert recorder["path"].endswith("/discussions/d1/notes")
    finally:
        cli.close()


def test_create_mr_note_posts_to_merge_request_notes_endpoint() -> None:
    recorder: dict[str, str] = dict()

    def responder(request: httpx.Request) -> httpx.Response:
        recorder.update(
            dict(
                method=request.method,
                path=request.url.path,
                body=request.content.decode("utf-8"),
            )
        )
        return httpx.Response(201, json=dict(id=55, body="summary"))

    transport = httpx.MockTransport(responder)
    cli = GitLabMrClient(base_url="https://gitlab.invalid", token="token", timeout_seconds=6.0, transport=transport)
    try:
        out = cli.create_mr_note(project="grp/proj", mr_iid=9, body="LGTM overall")
        assert out["id"] == 55
        assert recorder["method"] == "POST"
        assert json.loads(recorder["body"]) == dict(body="LGTM overall")
        assert recorder["path"].endswith("/merge_requests/9/notes")
        assert "/discussions/" not in recorder["path"]
    finally:
        cli.close()


def test_create_mr_discussion_posts_position_and_body() -> None:
    recorder: dict[str, str] = dict()

    def responder(request: httpx.Request) -> httpx.Response:
        recorder.update(
            dict(
                method=request.method,
                path=request.url.path,
                body=request.content.decode("utf-8"),
            )
        )
        return httpx.Response(201, json=dict(id="thread-1"))

    transport = httpx.MockTransport(responder)
    cli = GitLabMrClient(base_url="https://gitlab.invalid", token="token", timeout_seconds=6.0, transport=transport)
    position = dict(
        position_type="text",
        base_sha="b",
        head_sha="h",
        start_sha="s",
        new_path="a.py",
        old_path="a.py",
        new_line=3,
    )
    try:
        out = cli.create_mr_discussion(
            project="grp/proj",
            mr_iid=2,
            body="inline nit",
            position=position,
        )
        assert out["id"] == "thread-1"
        payload = json.loads(recorder["body"])
        assert payload["body"] == "inline nit"
        assert payload["position"]["new_line"] == 3
        assert recorder["path"].endswith("/merge_requests/2/discussions")
    finally:
        cli.close()


def test_approve_merge_request_posts_to_approve_endpoint() -> None:
    recorder: dict[str, str] = dict()

    def responder(request: httpx.Request) -> httpx.Response:
        recorder.update(
            dict(
                method=request.method,
                path=request.url.path,
                body=request.content.decode("utf-8") if request.content else "",
            )
        )
        return httpx.Response(200, json=dict(iid=9, approved=True))

    transport = httpx.MockTransport(responder)
    cli = GitLabMrClient(base_url="https://gitlab.invalid", token="token", timeout_seconds=6.0, transport=transport)
    try:
        out = cli.approve_merge_request(
            project="grp/proj",
            mr_iid=9,
            sha="abc123",
            approval_password="secret",
        )
        assert out["approved"] is True
        assert recorder["method"] == "POST"
        assert recorder["path"].endswith("/merge_requests/9/approve")
        payload = json.loads(recorder["body"])
        assert payload == dict(sha="abc123", approval_password="secret")
    finally:
        cli.close()


def test_approve_merge_request_empty_body_when_no_options() -> None:
    recorder: dict[str, str] = dict()

    def responder(request: httpx.Request) -> httpx.Response:
        recorder["body"] = request.content.decode("utf-8") if request.content else ""
        return httpx.Response(200, json=dict(iid=3))

    transport = httpx.MockTransport(responder)
    cli = GitLabMrClient(base_url="https://gitlab.invalid", token="token", timeout_seconds=6.0, transport=transport)
    try:
        cli.approve_merge_request(project="grp/proj", mr_iid=3)
        assert recorder["body"] == ""
    finally:
        cli.close()


def test_create_merge_request_includes_optional_description_when_present() -> None:
    storage: dict[str, str] = dict()

    def responder(request: httpx.Request) -> httpx.Response:
        storage["blob"] = request.content.decode("utf-8")
        return httpx.Response(201, json=dict(iid=7, web_url="https://gitlab.invalid/demo/-/merge_requests/7"))

    transport = httpx.MockTransport(responder)
    cli = GitLabMrClient(base_url="https://gitlab.invalid", token="z", timeout_seconds=2.0, transport=transport)
    try:
        mr = cli.create_merge_request(
            project="grp/proj",
            source_branch="a",
            target_branch="b",
            title="feat",
            description="content",
        )
        decoded = json.loads(storage["blob"])
        expected = dict(source_branch="a", target_branch="b", title="feat", description="content")
        assert decoded == expected
        assert mr["iid"] == 7
    finally:
        cli.close()
