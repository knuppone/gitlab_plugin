from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict, Union


class AuthorDict(TypedDict, total=False):
    id: int
    username: str
    name: str
    avatar_url: str
    web_url: str


class DiscussionNoteNormalized(TypedDict, total=False):
    id: int
    discussion_id: str
    noteable_type: Optional[str]
    body: Optional[str]
    author: Union[AuthorDict, Dict[str, Any]]
    created_at: Optional[str]
    updated_at: Optional[str]
    resolved: Optional[bool]


class DiscussionPositionTyped(TypedDict, total=False):
    old_path: Optional[str]
    new_path: Optional[str]
    base_sha: Optional[str]
    head_sha: Optional[str]
    start_sha: Optional[str]
    new_line: Optional[int]
    old_line: Optional[int]
    position_type: Optional[str]


class DiscussionNormalized(TypedDict):
    discussion_id: str
    resolved: Optional[bool]
    position: Union[DiscussionPositionTyped, Dict[str, Any], None]
    notes: List[DiscussionNoteNormalized]
