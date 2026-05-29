# Cursor skills (gitlab-mr-cli)

Use **`gitlab-mr-cli`** (`.cursor/skills/gitlab-mr-cli/SKILL.md`) for merge request review threads, comments, and approvals.

## Create a PR / MR

GitLab calls these **merge requests**; `gitlab-mr pr` is an alias of `create`.

**Target branch:** open the MR into the branch this feature branch was **originally created from** — not `main` by default. If `feature/US-123456` was branched from `dev`, merge **`feature/US-123456` → `dev`**.

1. Resolve branches:
   - **`--source-branch`**: current branch (`git branch --show-current`).
   - **`--target-branch`**: parent branch at creation (e.g. `dev`). If you used `git checkout -b feature/US-123456 dev`, target is **`dev`**. When unsure, check reflog: `git reflog | grep "moving from"` near branch creation, or ask the user.
2. Push **`source_branch`** to the remote.
3. Set **`GITLAB_TOKEN`** with **`api`** scope.
4. Run:

```bash
SOURCE="$(git branch --show-current)"
TARGET=dev   # branch you forked from, not main unless that was the parent

gitlab-mr pr --project acme/widget \
  --source-branch "$SOURCE" --target-branch "$TARGET" \
  --title "Add foo" --description "Summary for reviewers."
```

Description is optional: use **`--description`**, **`--description-file`**, or pipe stdin. Add **`--dry-run`** to print resolved fields without calling GitLab.
