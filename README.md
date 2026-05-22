# gitlab-mr-cli

JSON-first CLI around the GitLab Merge Request REST API (`discussions`, inline `inline` threads on file/line, top-level `comment`/`note`, threaded `reply`) and opening new MRs, meant for scripted and agent-driven review workflows.

Documentation: [Merge requests API](https://docs.gitlab.com/ee/api/merge_requests.html), [Discussions API](https://docs.gitlab.com/ee/api/discussions.html), [Notes API](https://docs.gitlab.com/ee/api/notes.html).

## Setup

- Python 3.10+
- PAT in **`GITLAB_TOKEN`** ([scopes](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html): **`read_api`** for read-only; **`api`** for comments, replies, approvals, and MR creation)
- Optional **`GITLAB_URL`** for self-managed installs (omit for https://gitlab.com)

```bash
python3 -m venv .venv
source .venv/bin/activate    # POSIX shell
pip install -e ".[dev]"
```

On macOS/Linux with PEP 668–managed interpreters, installing into an activated venv (as shown) avoids `pip` permission errors.

```bash
gitlab-mr discussions --help
```

## Usage

### List review threads (`discussions` / `review-comments`)

Parses HTTPS MR URLs or numeric **IID** with `--project`:

```bash
gitlab-mr discussions "https://gitlab.com/acme/widget/-/merge_requests/12"

gitlab-mr review-comments 12 --project acme/widget --max-pages 3 --compact
```

`--dry-run` prints resolved routing metadata without contacting GitLab (token not required).

Output is a JSON object with **`source_branch`** (feature branch) and **`discussions`** (thread list). Default **`--format agent`** is slim for automation; **`--format full`** keeps verbose author objects, raw `position`, and note ids.

```bash
gitlab-mr discussions "https://gitlab.com/acme/widget/-/merge_requests/12" --compact \
  | jq '{branch: .source_branch, threads: [.discussions[] | .discussion_id]}'
```

### Start an inline review thread (`inline`)

First comment on a file/line must include GitLab `position` (not `comment` / bare `reply`):

```bash
gitlab-mr inline "https://gitlab.com/acme/widget/-/merge_requests/12" \
  --file src/widget.py --line 88 --body "Consider null guard here." \
  --resolve-shas mr

gitlab-mr inline 12 --project acme/widget --file src/widget.py --line 10 --line-end 12 \
  --body "Style: merge these branches." --resolve-shas git --target-branch main
```

`--resolve-shas mr` uses MR `diff_refs`; `git` uses local `HEAD`, `origin/<target>`, and `merge-base`. Override with `--base-sha`, `--head-sha`, `--start-sha`.

### Add a top-level MR comment (`comment` / `note`)

Posts to the merge request **notes** endpoint (summary comment on the MR, not inside a review thread). Same body options as `reply` (`--body`, `--body-file`, stdin).

```bash
gitlab-mr comment "https://gitlab.com/acme/widget/-/merge_requests/12" \
  --body "Reviewed end-to-end; ready to merge after CI."

printf "LGTM from agent." | gitlab-mr note 12 --project acme/widget
```

### Reply in a discussion thread

Use `discussion_id` from JSON above (inline / threaded review feedback).

```bash
# After saving discussions output to mr.json:
printf "Adjusted per review." | gitlab-mr reply 12 --project acme/widget \
  --discussion-id "$(jq -r '.discussions[0].discussion_id' mr.json)"

gitlab-mr reply "https://gitlab.com/acme/widget/-/merge_requests/12" \
  --discussion-id abc123deadbeef --body-file reply.md
```

### Approve a merge request (`approve`)

Records your approval on the MR (does **not** merge). Requires **`api`** scope. Optional **`--sha`** (commit SHA) or **`--sha mr`** to approve the current MR HEAD; **`--approval-password`** when the project requires re-authentication.

```bash
gitlab-mr approve "https://gitlab.com/acme/widget/-/merge_requests/12"
gitlab-mr approve 12 --project acme/widget --sha mr --compact
```

### Create a merge request

Requires branches that already exist on the remote (`source_branch` / `target_branch`). Supply description via **`--description`**, **`--description-file`**, or **piped stdin** (TTY stdin alone errors).

```bash
cat descr.md | gitlab-mr create --project acme/widget \
  --source-branch feat/foo --target-branch main --title "Add foo"
```

## Recommended follow-up CLI features

1. **`show`** MR metadata — state, pipelines, approvals at a glance (beyond `source_branch` in `discussions`).
2. **`diff`** / **`changes`** export — grounding models on code beside comments.
3. **`pipelines`** + **`job-trace`** — shorten CI-fix loops.
4. **`resolve-discussion`** — mark review threads addressed programmatically.
5. **`--dry-run` improvements** — redacted HTTP preview consistently across commands.
