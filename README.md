# gitlab-mr-cli

JSON-first CLI around the GitLab Merge Request REST API (`discussions` + threaded `reply`) and opening new MRs, meant for scripted and agent-driven review workflows.

Documentation: [Merge requests API](https://docs.gitlab.com/ee/api/merge_requests.html), [Discussions API](https://docs.gitlab.com/ee/api/discussions.html).

## Setup

- Python 3.10+
- PAT in **`GITLAB_TOKEN`** ([scopes](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html): **`read_api`** for read-only; **`api`** for replies and MR creation)
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

### Reply in a discussion thread

Use `discussion_id` from JSON above.

```bash
# After saving discussions output to mr.json:
printf "Adjusted per review." | gitlab-mr reply 12 --project acme/widget \
  --discussion-id "$(jq -r '.[0].discussion_id' mr.json)"

gitlab-mr reply "https://gitlab.com/acme/widget/-/merge_requests/12" \
  --discussion-id abc123deadbeef --body-file reply.md
```

### Create a merge request

Requires branches that already exist on the remote (`source_branch` / `target_branch`). Supply description via **`--description`**, **`--description-file`**, or **piped stdin** (TTY stdin alone errors).

```bash
cat descr.md | gitlab-mr create --project acme/widget \
  --source-branch feat/foo --target-branch main --title "Add foo"
```

## Recommended follow-up CLI features

1. **`show`** MR metadata — state, pipelines, approvals at a glance.
2. **`diff`** / **`changes`** export — grounding models on code beside comments.
3. **`pipelines`** + **`job-trace`** — shorten CI-fix loops.
4. **`resolve-discussion`** / **`note`** — mark threads addressed or drop summary notes off-thread.
5. **`--dry-run` improvements** — redacted HTTP preview consistently across commands.
