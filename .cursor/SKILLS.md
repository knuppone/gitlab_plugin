# Cursor skills (gitlab-mr-cli)

Use **`gitlab-mr-cli`** (`.cursor/skills/gitlab-mr-cli/SKILL.md`) for merge request review threads, comments, and approvals.

## Create a PR / MR

GitLab calls these **merge requests**; `gitlab-mr pr` is an alias of `create`.

1. Push `source_branch` to the remote.
2. Set **`GITLAB_TOKEN`** with **`api`** scope.
3. Run:

```bash
gitlab-mr pr --project acme/widget \
  --source-branch feat/foo --target-branch main \
  --title "Add foo" --description "Summary for reviewers."
```

Description is optional: use **`--description`**, **`--description-file`**, or pipe stdin. Add **`--dry-run`** to print resolved fields without calling GitLab.
