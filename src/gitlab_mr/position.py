from __future__ import annotations

import hashlib
from typing import Any, Dict, Mapping, Optional


def _line_code(file_path: str, old_line: int, new_line: int) -> str:
    digest = hashlib.sha1(file_path.encode("utf-8")).hexdigest()
    return f"{digest}_{old_line}_{new_line}"


def diff_refs_from_mr(mr: Mapping[str, Any]) -> Dict[str, str]:
    refs_raw = mr.get("diff_refs")
    if not isinstance(refs_raw, Mapping):
        raise ValueError("merge request has no diff_refs (MR may still be initializing)")
    refs: Dict[str, Any] = dict(refs_raw)
    missing = [key for key in ("base_sha", "head_sha", "start_sha") if not str(refs.get(key, "")).strip()]
    if missing:
        raise ValueError(f"diff_refs missing: {', '.join(missing)}")
    return dict(
        base_sha=str(refs["base_sha"]).strip(),
        head_sha=str(refs["head_sha"]).strip(),
        start_sha=str(refs["start_sha"]).strip(),
    )


def normalize_file_path(raw: str) -> str:
    trimmed = raw.strip()
    if trimmed.startswith("./"):
        return trimmed[2:]
    return trimmed


def build_text_position(
    *,
    file_path: str,
    new_line: int,
    old_line: Optional[int] = None,
    new_line_end: Optional[int] = None,
    old_line_end: Optional[int] = None,
    base_sha: str,
    head_sha: str,
    start_sha: str,
    line_type: str = "new",
) -> Dict[str, Any]:
    """Build GitLab `position` for a new MR diff discussion (text)."""
    path = normalize_file_path(file_path)
    if new_line < 1:
        raise ValueError("line must be >= 1")
    if new_line_end is not None and new_line_end < new_line:
        raise ValueError("line-end must be >= line")

    base_fields: Dict[str, Any] = dict(
        position_type="text",
        base_sha=base_sha.strip(),
        head_sha=head_sha.strip(),
        start_sha=start_sha.strip(),
        new_path=path,
        old_path=path,
    )

    if new_line_end is None or new_line_end == new_line:
        payload = dict(**base_fields, new_line=new_line)
        if old_line is not None:
            payload["old_line"] = old_line
        return payload

    start_old = old_line if old_line is not None else new_line
    end_old = old_line_end if old_line_end is not None else (old_line if old_line is not None else new_line_end)
    return dict(
        **base_fields,
        line_range=dict(
            start=dict(
                line_code=_line_code(path, start_old, new_line),
                type=line_type,
                old_line=start_old,
                new_line=new_line,
            ),
            end=dict(
                line_code=_line_code(path, end_old, new_line_end),
                type=line_type,
                old_line=end_old,
                new_line=new_line_end,
            ),
        ),
    )
