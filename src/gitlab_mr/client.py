from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Union, cast

import httpx

from gitlab_mr.models import DiscussionNormalized, DiscussionNoteNormalized


class GitLabMrClient:
    """Minimal GitLab REST client for merge request discussions."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_seconds: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        root = base_url.strip().rstrip("/")
        if not root:
            raise ValueError("base_url must not be empty")
        self._base_url: str = root
        client_kw: Dict[str, Any] = dict(
            base_url=f"{root}/api/v4",
            headers=dict((("PRIVATE-TOKEN", token.strip()),)),
            timeout=timeout_seconds,
        )
        if transport is not None:
            client_kw["transport"] = transport
        self._client = httpx.Client(**client_kw)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GitLabMrClient":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[Any],
    ) -> None:
        self.close()

    def _project_segment(self, project: Union[str, int]) -> str:
        return str(project) if isinstance(project, int) else project.replace("/", "%2F")

    def list_mr_discussions_paginated(
        self,
        *,
        project: Union[str, int],
        mr_iid: int,
        per_page: int = 20,
        max_pages: Optional[int] = None,
    ) -> List[Mapping[str, Any]]:
        encoded = self._project_segment(project)
        path = f"/projects/{encoded}/merge_requests/{mr_iid}/discussions"
        page: int = 1
        pages_fetched: int = 0
        collected: List[Mapping[str, Any]] = []
        while True:
            if max_pages is not None and pages_fetched >= max_pages:
                break
            resp = self._client.get(path, params=dict(per_page=str(per_page), page=str(page)))
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                items: Sequence[Mapping[str, Any]] = cast(List[Mapping[str, Any]], data)
                pages_fetched += 1
                collected.extend(list(items))
                if len(items) < per_page:
                    break
                page += 1
            else:
                raise RuntimeError(f"unexpected discussions payload: {type(data)}")
        return collected

    def reply_to_discussion(
        self,
        *,
        project: Union[str, int],
        mr_iid: int,
        discussion_id: str,
        body: str,
    ) -> Mapping[str, Any]:
        encoded = self._project_segment(project)
        path = f"/projects/{encoded}/merge_requests/{mr_iid}/discussions/{discussion_id}/notes"
        resp = self._client.post(path, json=dict(body=body))
        resp.raise_for_status()
        return cast(Mapping[str, Any], resp.json())

    def create_mr_note(
        self,
        *,
        project: Union[str, int],
        mr_iid: int,
        body: str,
    ) -> Mapping[str, Any]:
        """Post a top-level merge request note (not a threaded discussion reply)."""
        encoded = self._project_segment(project)
        path = f"/projects/{encoded}/merge_requests/{mr_iid}/notes"
        resp = self._client.post(path, json=dict(body=body))
        resp.raise_for_status()
        return cast(Mapping[str, Any], resp.json())

    def create_merge_request(
        self,
        *,
        project: Union[str, int],
        source_branch: str,
        target_branch: str,
        title: str,
        description: str = "",
    ) -> Mapping[str, Any]:
        encoded = self._project_segment(project)
        payload = dict(
            source_branch=source_branch,
            target_branch=target_branch,
            title=title,
        )
        if description.strip():
            payload["description"] = description
        path = f"/projects/{encoded}/merge_requests"
        resp = self._client.post(path, json=payload)
        resp.raise_for_status()
        return cast(Mapping[str, Any], resp.json())


def _parse_iso_datetime(raw: Optional[str]) -> Tuple[int, datetime]:
    if raw is None or raw == "":
        return (0, datetime.min)
    trimmed = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(trimmed)
    epoch = datetime(1970, 1, 1, tzinfo=parsed.tzinfo)
    return int((parsed - epoch).total_seconds()), parsed


def normalize_discussions(discussions: Sequence[Mapping[str, Any]]) -> List[DiscussionNormalized]:
    result: List[DiscussionNormalized] = []
    for item in discussions:
        discussion_id = str(item["id"]) if item.get("id") is not None else ""
        if not discussion_id:
            raise ValueError("discussion missing id")
        position_raw = item.get("position")
        position_payload: Dict[str, Any] | None
        if isinstance(position_raw, Mapping):
            position_payload = dict(position_raw)
        else:
            position_payload = None
        resolved_flag: Optional[bool] = None
        if "resolved" in item:
            resolved_value = item.get("resolved")
            if isinstance(resolved_value, bool):
                resolved_flag = resolved_value

        notes_field = item.get("notes")
        notes_in: List[Mapping[str, Any]]
        if isinstance(notes_field, list):
            notes_in = cast(List[Mapping[str, Any]], notes_field)
        else:
            notes_in = []

        note_resolved_fallback: Optional[bool] = resolved_flag

        def pick_resolved(note: Mapping[str, Any]) -> Optional[bool]:
            if "resolved" in note:
                vr = note.get("resolved")
                if isinstance(vr, bool):
                    return vr
            return note_resolved_fallback

        normalized_notes_raw: List[DiscussionNoteNormalized] = []
        for note in sorted(
            notes_in,
            key=lambda n: (_parse_iso_datetime(cast(Optional[str], n.get("created_at"))))[0],
        ):
            mutable: MutableMapping[str, Any] = dict(
                id=int(note["id"]),
                discussion_id=str(discussion_id),
                noteable_type=cast(Optional[str], note.get("noteable_type")),
                body=cast(Optional[str], note.get("body")),
                author=dict(note["author"]) if isinstance(note.get("author"), Mapping) else {},
                created_at=cast(Optional[str], note.get("created_at")),
                updated_at=cast(Optional[str], note.get("updated_at")),
                resolved=pick_resolved(note),
            )
            normalized_notes_raw.append(cast(DiscussionNoteNormalized, dict(**mutable)))

        discussion_payload: DiscussionNormalized = cast(
            DiscussionNormalized,
            dict(
                discussion_id=str(discussion_id),
                resolved=resolved_flag,
                position=position_payload,
                notes=normalized_notes_raw,
            ),
        )
        result.append(discussion_payload)
    return sorted(result, key=lambda thread: (_first_note_datetime(thread)[0]))


def _parse_iso_normalized(note: DiscussionNoteNormalized) -> Tuple[int, datetime]:
    return _parse_iso_datetime(cast(Optional[str], note.get("created_at")))


def _first_note_datetime(discussion: DiscussionNormalized) -> Tuple[int, datetime]:
    notes_seq: List[DiscussionNoteNormalized] = discussion.get("notes", [])
    if not notes_seq:
        return _parse_iso_datetime("")
    return _parse_iso_normalized(cast(DiscussionNoteNormalized, notes_seq[0]))


def dump_json_stdout(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False)
