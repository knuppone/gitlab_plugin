import pytest

from gitlab_mr.parsing import MrReference, normalize_project_segment, parse_merge_request_identifier


def test_parse_https_merge_request_without_extra_project_argument() -> None:
    mr = parse_merge_request_identifier(
        "https://gitlab.acme.biz/acme/widget/-/merge_requests/23",
        None,
    )
    assert mr.project == "acme/widget"
    assert mr.iid == 23


def test_conflict_when_project_override_mismatches_url_path() -> None:
    with pytest.raises(ValueError, match="does not match"):
        parse_merge_request_identifier(
            "https://gitlab.com/acme/repo/-/merge_requests/1",
            "other/repo",
        )


@pytest.mark.parametrize(
    ("raw_project",),
    [(value,) for value in ("acme/repo", "/acme/repo/", " acme/repo ")],
)
def test_normalize_project_segment_trims(raw_project: str) -> None:
    assert normalize_project_segment(raw_project) == "acme/repo"


def test_numeric_identifier_with_project_returns_reference() -> None:
    mr = parse_merge_request_identifier("42", "acme/app")
    assert mr == MrReference(project="acme/app", iid=42)


def test_numeric_identifier_without_project_rejected() -> None:
    with pytest.raises(ValueError, match="--project"):
        parse_merge_request_identifier("42", None)
