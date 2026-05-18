from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Union
from urllib.parse import unquote, urlparse


_NON_DIGIT_PATTERN: Final[re.Pattern[str]] = re.compile(r"\D")


@dataclass(frozen=True, slots=True)
class MrReference:
    project: Union[str, int]
    iid: int


def normalize_project_segment(raw: str) -> str:
    cleaned: str = raw.strip().strip("/")
    return cleaned


def parse_mr_url(url: str) -> MrReference:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("merge request URL must include scheme and host")
    path = unquote(parsed.path or "")
    marker = "/-/merge_requests/"
    idx = path.find(marker)
    if idx < 0:
        raise ValueError("could not find /-/merge_requests/ in URL")
    project_part = normalize_project_segment(path[:idx])
    remainder = path[idx + len(marker) :]
    iid_part = remainder.split("/")[0]
    digits = "".join(ch for ch in iid_part if ch.isdigit())
    if not digits:
        raise ValueError("could not parse merge request IID from URL")
    return MrReference(project=project_part, iid=int(digits))


def looks_like_mr_url(candidate: str) -> bool:
    text = candidate.strip()
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return False
    return "/-/merge_requests/" in (unquote(parsed.path or ""))


def parse_merge_request_identifier(
    value: str, project: Union[str, int, None]
) -> MrReference:
    text = value.strip()
    if looks_like_mr_url(text):
        ref = parse_mr_url(text)
        if project is not None:
            normalized = normalize_project_segment(str(project))
            merged = normalized if normalized else None
            if merged is None:
                return ref
            if isinstance(ref.project, str) and ref.project != merged:
                raise ValueError(
                    "project from --project does not match project parsed from URL"
                )
        return ref
    digits = _NON_DIGIT_PATTERN.sub("", text.split()[0])
    if not digits.isdigit():
        raise ValueError(
            "expected merge request URL or numeric IID together with --project"
        )
    if project is None:
        raise ValueError("--project is required when passing a numeric IID instead of URL")
    return MrReference(project=project, iid=int(digits))
