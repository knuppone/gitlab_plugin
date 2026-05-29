---
name: gitlab-mr-cli-shell
description: >-
  gitlab-mr for MR threads/notes and opening PRs; review code on local checkout of source_branch. Triggers: gitlab-mr, MR URL, MR review, create PR.
---

# gitlab-mr CLI

JSON-first GitLab MR CLI. Auth: **`GITLAB_TOKEN`** (optional **`GITLAB_URL`**). Common flags: `--compact`, `--dry-run`, `--verbose`, `--timeout`, `--gitlab-url`, `--token`.

Run **`gitlab-mr --help`** or **`gitlab-mr <command> --help`** for further info. **`gitlab-mr -V`** for version.

`discussions` also: `--per-page`, `--max-pages`, `--format agent|full` (default **agent**), `-p` / `--project` with numeric IID.

## Commands

| Command | Alias | Action |
|---------|-------|--------|
| `discussions` | `review-comments` | `GET` → `{source_branch, discussions[]}` |
| `inline` | — | `POST` new inline thread (`--file`, `--line`, SHAs) |
| `comment` | `note` | `POST` top-level MR note |
| `reply` | — | `POST` in thread (`--discussion-id`) |
| `approve` | — | `POST` approve as current user (not merge); needs **`api`** |
| `create` | `pr` | `POST` new MR (pull request) |

MR id: full URL `…/merge_requests/12` or IID + `--project ns/repo`. Body: `--body`, `--body-file`, or stdin (`comment`/`note`/`reply`/`inline`). `create`/`pr`: `--description` / file / stdin; branches must exist on remote.

**`create` / `pr` branches:** `--source-branch` = current feature branch; `--target-branch` = branch it was **originally forked from** (e.g. `feature/US-123456` → `dev` when created from `dev`). Do not default to `main` unless that was the parent. Confirm via creation command or `git reflog | grep "moving from"`.

```bash
SOURCE="$(git branch --show-current)"
TARGET=dev   # parent at branch creation

gitlab-mr pr --project acme/widget --source-branch "$SOURCE" --target-branch "$TARGET" \
  --title "Add x" -d "What changed and how to test."
```

## Review workflow

- Do **not** fetch MR diffs/files from GitLab; use local git on **`source_branch`** from `discussions` JSON.
- Match `git remote` to project in URL; else stop and ask user to open the right clone.
- `git fetch origin` → `git switch <source_branch>` (or track `origin/<source_branch>`).
- Thread with **`position`**: read `position.file` at `position.line` locally before triaging. No `position` → MR-wide note only.
- New inline on code → **`inline`**. Follow-up → **`reply`**. MR-wide → **`comment`**. Do not use `comment`/`reply` for first inline (needs `position`).

```bash
gitlab-mr discussions "…/586" --compact \
  | jq '.discussions[] | {id: .discussion_id, at: .position, first: .notes[0].body}'
jq -r '.source_branch'   # branch for git switch

DISC="$(gitlab-mr discussions "…/586" --compact | jq -r '.discussions[0].discussion_id')"
gitlab-mr reply "…/586" --discussion-id "$DISC" --body "Fixed."
gitlab-mr inline "…/586" --file src/foo.py --line 42 --body "nit" --resolve-shas mr
gitlab-mr approve "…/586"              # optional: --sha mr
```

Agent thread shape: slim `author` string; inline has `position: {file, line}` (optional `line_end`). `--format full` for verbose/raw fields.
