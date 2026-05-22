from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Mapping, MutableMapping, Optional, Sequence, Tuple, Union, cast

import httpx

from gitlab_mr.models import (
    DiscussionAgent,
    DiscussionNormalized,
    DiscussionNoteAgent,
    DiscussionNoteNormalized,
    DiscussionPositionSlim,
    DiscussionsEnvelope,
)

DiscussionsOutputFormat = Literal["agent", "full"]


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

    def get_merge_request(
        self,
        *,
        project: Union[str, int],
        mr_iid: int,
    ) -> Mapping[str, Any]:
        encoded = self._project_segment(project)
        path = f"/projects/{encoded}/merge_requests/{mr_iid}"
        resp = self._client.get(path)
        resp.raise_for_status()
        return cast(Mapping[str, Any], resp.json())

    def create_mr_discussion(
        self,
        *,
        project: Union[str, int],
        mr_iid: int,
        body: str,
        position: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Open a new MR discussion thread with an inline diff position."""
        encoded = self._project_segment(project)
        path = f"/projects/{encoded}/merge_requests/{mr_iid}/discussions"
        resp = self._client.post(path, json=dict(body=body, position=dict(position)))
        resp.raise_for_status()
        return cast(Mapping[str, Any], resp.json())

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

    def approve_merge_request(
        self,
        *,
        project: Union[str, int],
        mr_iid: int,
        sha: Optional[str] = None,
        approval_password: Optional[str] = None,
    ) -> Mapping[str, Any]:
        encoded = self._project_segment(project)
        path = f"/projects/{encoded}/merge_requests/{mr_iid}/approve"
        body: Dict[str, str] = dict()
        if sha is not None and sha.strip():
            body["sha"] = sha.strip()
        if approval_password is not None and approval_password.strip():
            body["approval_password"] = approval_password.strip()
        resp = self._client.post(path, json=body if body else None)
        resp.raise_for_status()
        return cast(Mapping[str, Any], resp.json())


def _parse_iso_datetime(raw: Optional[str]) -> Tuple[int, datetime]:
    if raw is None or raw == "":
        return (0, datetime.min)
    trimmed = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(trimmed)
    epoch = datetime(1970, 1, 1, tzinfo=parsed.tzinfo)
    return int((parsed - epoch).total_seconds()), parsed


def _discussion_resolved(item: Mapping[str, Any]) -> Optional[bool]:
    resolved_value = item.get("resolved")
    if isinstance(resolved_value, bool):
        return resolved_value
    return None


def _note_resolved(note: Mapping[str, Any], thread_resolved: Optional[bool]) -> Optional[bool]:
    resolved_value = note.get("resolved")
    if isinstance(resolved_value, bool):
        return resolved_value
    return thread_resolved


def _slim_author(author_raw: Any) -> str:
    if isinstance(author_raw, Mapping):
        username = author_raw.get("username")
        if username is not None and str(username).strip():
            return str(username).strip()
        name = author_raw.get("name")
        if name is not None and str(name).strip():
            return str(name).strip()
    return ""


def _slim_position(position_raw: Mapping[str, Any]) -> DiscussionPositionSlim:
    file_path = str(position_raw.get("new_path") or position_raw.get("old_path") or "").strip()
    if not file_path:
        raise ValueError("position missing file path")

    slim: Dict[str, Any] = dict(file=file_path)
    line_range_raw = position_raw.get("line_range")
    if isinstance(line_range_raw, Mapping):
        start_raw = line_range_raw.get("start")
        end_raw = line_range_raw.get("end")
        if isinstance(start_raw, Mapping):
            start_new = start_raw.get("new_line")
            start_old = start_raw.get("old_line")
            if start_new is not None:
                slim["line"] = int(start_new)
            elif start_old is not None:
                slim["line"] = int(start_old)
        if isinstance(end_raw, Mapping):
            end_new = end_raw.get("new_line")
            end_old = end_raw.get("old_line")
            end_line = end_new if end_new is not None else end_old
            if end_line is not None:
                end_int = int(end_line)
                if slim.get("line") != end_int:
                    slim["line_end"] = end_int
        return cast(DiscussionPositionSlim, slim)

    new_line = position_raw.get("new_line")
    old_line = position_raw.get("old_line")
    if new_line is not None:
        slim["line"] = int(new_line)
    if old_line is not None:
        old_int = int(old_line)
        if new_line is None:
            slim["line"] = old_int
        elif int(new_line) != old_int:
            slim["old_line"] = old_int
    if "line" not in slim:
        raise ValueError("position missing line number")
    return cast(DiscussionPositionSlim, slim)


def _sorted_notes(notes_in: List[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    return sorted(
        notes_in,
        key=lambda note: (_parse_iso_datetime(cast(Optional[str], note.get("created_at"))))[0],
    )


def _normalize_discussions_full(discussions: Sequence[Mapping[str, Any]]) -> List[DiscussionNormalized]:
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
        resolved_flag = _discussion_resolved(item)

        notes_field = item.get("notes")
        notes_in: List[Mapping[str, Any]]
        if isinstance(notes_field, list):
            notes_in = cast(List[Mapping[str, Any]], notes_field)
        else:
            notes_in = []

        normalized_notes_raw: List[DiscussionNoteNormalized] = []
        for note in _sorted_notes(notes_in):
            mutable: MutableMapping[str, Any] = dict(
                id=int(note["id"]),
                discussion_id=str(discussion_id),
                noteable_type=cast(Optional[str], note.get("noteable_type")),
                body=cast(Optional[str], note.get("body")),
                author=dict(note["author"]) if isinstance(note.get("author"), Mapping) else {},
                created_at=cast(Optional[str], note.get("created_at")),
                updated_at=cast(Optional[str], note.get("updated_at")),
                resolved=_note_resolved(note, resolved_flag),
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
    return sorted(result, key=lambda thread: (_first_note_datetime_full(thread)[0]))


def _normalize_discussions_agent(discussions: Sequence[Mapping[str, Any]]) -> List[DiscussionAgent]:
    result: List[DiscussionAgent] = []
    for item in discussions:
        discussion_id = str(item["id"]) if item.get("id") is not None else ""
        if not discussion_id:
            raise ValueError("discussion missing id")
        resolved_flag = _discussion_resolved(item)

        notes_field = item.get("notes")
        notes_in: List[Mapping[str, Any]]
        if isinstance(notes_field, list):
            notes_in = cast(List[Mapping[str, Any]], notes_field)
        else:
            notes_in = []

        agent_notes: List[DiscussionNoteAgent] = []
        for note in _sorted_notes(notes_in):
            author_label = _slim_author(note.get("author"))
            note_payload: DiscussionNoteAgent = cast(
                DiscussionNoteAgent,
                dict(
                    body=cast(Optional[str], note.get("body")),
                    created_at=cast(Optional[str], note.get("created_at")),
                    resolved=_note_resolved(note, resolved_flag),
                ),
            )
            if author_label:
                note_payload["author"] = author_label
            agent_notes.append(note_payload)

        thread_payload: Dict[str, Any] = dict(
            discussion_id=str(discussion_id),
            resolved=resolved_flag,
            notes=agent_notes,
        )
        position_raw = item.get("position")
        if isinstance(position_raw, Mapping):
            thread_payload["position"] = _slim_position(position_raw)
        result.append(cast(DiscussionAgent, thread_payload))
    return sorted(result, key=lambda thread: (_first_note_datetime_agent(thread)[0]))


def normalize_discussions(
    discussions: Sequence[Mapping[str, Any]],
    *,
    output_format: DiscussionsOutputFormat = "agent",
) -> Union[List[DiscussionAgent], List[DiscussionNormalized]]:
    if output_format == "full":
        return _normalize_discussions_full(discussions)
    if output_format == "agent":
        return _normalize_discussions_agent(discussions)
    raise ValueError(f"unknown discussions output format: {output_format}")


def build_discussions_envelope(
    mr: Mapping[str, Any],
    discussions: Sequence[Mapping[str, Any]],
    *,
    output_format: DiscussionsOutputFormat = "agent",
) -> DiscussionsEnvelope:
    source_branch_raw = mr.get("source_branch")
    if source_branch_raw is None or str(source_branch_raw).strip() == "":
        raise ValueError("merge request missing source_branch")
    threads = normalize_discussions(discussions, output_format=output_format)
    return cast(
        DiscussionsEnvelope,
        dict(
            source_branch=str(source_branch_raw).strip(),
            discussions=threads,
        ),
    )


def _parse_iso_normalized(note: Mapping[str, Any]) -> Tuple[int, datetime]:
    return _parse_iso_datetime(cast(Optional[str], note.get("created_at")))


def _first_note_datetime_full(discussion: DiscussionNormalized) -> Tuple[int, datetime]:
    notes_seq: List[DiscussionNoteNormalized] = discussion.get("notes", [])
    if not notes_seq:
        return _parse_iso_datetime("")
    return _parse_iso_normalized(cast(DiscussionNoteNormalized, notes_seq[0]))


def _first_note_datetime_agent(discussion: DiscussionAgent) -> Tuple[int, datetime]:
    notes_seq: List[DiscussionNoteAgent] = discussion.get("notes", [])
    if not notes_seq:
        return _parse_iso_datetime("")
    return _parse_iso_normalized(cast(DiscussionNoteAgent, notes_seq[0]))


def dump_json_stdout(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False)
