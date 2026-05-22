import pytest

from gitlab_mr.position import build_text_position, diff_refs_from_mr


def test_build_text_position_single_line_added() -> None:
    pos = build_text_position(
        file_path="./src/a.py",
        new_line=10,
        base_sha="base",
        head_sha="head",
        start_sha="start",
    )
    assert pos["new_path"] == "src/a.py"
    assert pos["old_path"] == "src/a.py"
    assert pos["new_line"] == 10
    assert "old_line" not in pos
    assert "line_range" not in pos


def test_build_text_position_multiline() -> None:
    pos = build_text_position(
        file_path="src/a.py",
        new_line=10,
        new_line_end=12,
        base_sha="base",
        head_sha="head",
        start_sha="start",
    )
    assert "line_range" in pos
    assert pos["line_range"]["start"]["new_line"] == 10
    assert pos["line_range"]["end"]["new_line"] == 12


def test_diff_refs_from_mr_requires_fields() -> None:
    with pytest.raises(ValueError, match="diff_refs missing"):
        diff_refs_from_mr(dict(diff_refs=dict(base_sha="a", head_sha="h")))


def test_diff_refs_from_mr_ok() -> None:
    shas = diff_refs_from_mr(
        dict(
            diff_refs=dict(
                base_sha="bbb",
                head_sha="hhh",
                start_sha="sss",
            )
        )
    )
    assert shas["head_sha"] == "hhh"
