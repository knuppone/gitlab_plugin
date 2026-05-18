import json

import httpx

from gitlab_mr.client import GitLabMrClient, normalize_discussions


def test_normalize_discussion_threads_shape() -> None:
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
    normalized = normalize_discussions([blob])
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
