---
name: gitlab-mr-cli-shell
description: >-
  Use the repo-local Citlab CLI for GitLab MR discussions (JSON), threaded replies (discussion_id), and MR creation.
  Triggers: gitlab-mr, MR review threads, shell GitLab API.
---

# gitlab-mr CLI (shell skill)

Thin JSON-first wrapper around GitLab REST **`/merge_requests` + `/discussions`** for agents and scripts. Prefer Cursor **GitLab MCP** when the repo already exposes it; use this CLI when you only have a shell and **`GITLAB_TOKEN`**.

## Help and version

Every command accepts **`--help`** and **`-h`**. Root **`--version` / `-V`** prints the package version.

Examples:

```text
gitlab-mr -h
gitlab-mr discussions -h
```

## Typical workflow

1. **`discussions`** (alias **`review-comments`**) — list threaded review payloads:

   ```text
   gitlab-mr discussions "https://gitlab.com/ns/repo/-/merge_requests/12"
   gitlab-mr discussions 12 -p ns/repo
   ```

2. **`discussion_id`** — take from JSON; each thread has `notes[]` with bodies and authors.

3. **`reply`** — post inside that thread (`--discussion-id`, body via **`--body`**, **`--body-file`**, or stdin).

4. **`create`** — open an MR (**`--source-branch`**, **`--target-branch`**, **`--title`**, plus description via **`--description`**, **`--description-file`**, or piped stdin).
