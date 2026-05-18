---
name: gitlab-mr-cli-shell
description: >-
  Run gitlab-mr: MR discussions JSON, top-level comment/note, threaded reply (discussion_id), create MR.
  Triggers: gitlab-mr, GitLab MR URL, PR review comments, shell GitLab API.
---

# gitlab-mr CLI (shell skill)

JSON-first GitLab **merge request** CLI

## Help and global flags

- Every command: **`--help`** / **`-h`**
- Root: **`gitlab-mr -V`** / **`--version`**

Common options on most commands:

| Flag | Purpose |
|------|---------|
| `--gitlab-url` | Override `GITLAB_URL` |
| `--token` | Override `GITLAB_TOKEN` |
| `--compact` | Single-line JSON on stdout |
| `--verbose` | Extra stderr on errors |
| `--dry-run` | Print resolved routing only; no HTTP |
| `--timeout` | HTTP timeout seconds (default 30) |

`discussions` also: `--per-page`, `--max-pages`, `--project` / `-p` (required with numeric IID).

## Command reference

| Command | Alias | Action |
|---------|-------|--------|
| `discussions` | `review-comments` | `GET` threaded discussions → normalized JSON |
| `comment` | `note` | `POST` **top-level** MR note (general PR comment) |
| `reply` | — | `POST` note **inside** thread (`--discussion-id` required) |
| `create` | — | `POST` new merge request |

### MR identifier

Pass either:

1. Full HTTPS URL: `https://gitlab.com/ns/repo/-/merge_requests/12`
2. Numeric IID + **`--project ns/repo`**

### Body text (`comment`, `note`, `reply`)

Exactly one source:

- `--body "markdown"`
- `--body -` or omit `--body` → read **stdin**
- `--body-file path.md`

Empty body → exit 1.

### `create` description

`--description`, `--description-file`, or piped stdin (TTY with no input → error). Branches must already exist on GitLab.

## Agent workflows

### Read all review threads

```bash
gitlab-mr discussions "https://gitlab.com/ns/repo/-/merge_requests/586" --compact \
  | jq '.[] | {id: .discussion_id, resolved: .resolved, first: .notes[0].body}'
```

### Post top-level MR comment (not a thread reply)

```bash
gitlab-mr comment "https://gitlab.com/ns/repo/-/merge_requests/586" \
  --body "## Summary\nAddressed timeout concern in commit abc."

printf "LGTM after CI green." | gitlab-mr note 586 -p ns/repo
```

### Reply inside a review thread

```bash
DISC="$(gitlab-mr discussions "…/586" --compact | jq -r '.[2].discussion_id')"
gitlab-mr reply "…/586" --discussion-id "$DISC" --body "Fixed in latest push."
```

### Open MR

```bash
gitlab-mr create -p ns/repo \
  --source-branch feature/x --target-branch main \
  --title "feat: x" --description-file MR_DESC.md
```

### Validate parsing without API

```bash
gitlab-mr discussions "…/586" --dry-run
```

## `comment` vs `reply` (critical)

| Intent | Command |
|--------|---------|
| New comment on the MR (summary, status, not tied to inline thread) | **`comment`** or **`note`** |
| Answer a specific review thread | **`reply`** + **`--discussion-id`** from `discussions` JSON |

REST mapping:

- `comment` / `note` → `POST /projects/:id/merge_requests/:iid/notes`
- `reply` → `POST /projects/:id/merge_requests/:iid/discussions/:discussion_id/notes`

Using `reply` without a thread id is wrong for “add a PR comment.”
