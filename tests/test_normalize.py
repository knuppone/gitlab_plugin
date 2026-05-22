from gitlab_mr.client import _slim_author, _slim_position


def test_slim_author_prefers_username() -> None:
    assert _slim_author(dict(username="alice", name="Alice A")) == "alice"


def test_slim_position_multiline_range() -> None:
    pos = _slim_position(
        dict(
            new_path="src/x.ts",
            line_range=dict(
                start=dict(new_line=10, old_line=10),
                end=dict(new_line=12, old_line=12),
            ),
        )
    )
    assert pos["file"] == "src/x.ts"
    assert pos["line"] == 10
    assert pos["line_end"] == 12
