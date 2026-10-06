# contribreport

List everyone who has had a pull request merged into a GitHub repository, with their first and most recent merged pull request, as JSON.

Written for [LibreSign/libresign#8678](https://github.com/LibreSign/libresign/issues/8678): LibreSign invites new contributors to a survey after their first merged pull request, and wanted a reproducible list of people who contributed before that workflow existed, so a maintainer can review it by hand. The tool only lists -- it doesn't rank, score, classify or contact anyone.

## Requirements

- Python 3.8 or newer (standard library only, nothing to install)
- The [GitHub CLI](https://cli.github.com), logged in (`gh auth login`)

## Usage

```bash
python3 contribreport.py owner/repo > report.json
```

For example:

```bash
python3 contribreport.py LibreSign/libresign > libresign.json
jq -r '.contributors[] | "\(.first_merged_pr.merged_at)  \(.login)  (\(.merged_pr_count) merged)"' libresign.json
```

The report goes to stdout and errors go to stderr. The exit code is `0` on success, `1` if `gh` is missing or fails (in which case nothing is written to stdout, so you never get a partial report), and `2` if the repository isn't in `owner/repo` form.

## Output

```json
{
  "repository": "owner/repo",
  "contributors": [
    {
      "login": "woody",
      "profile_url": "https://github.com/woody",
      "merged_pr_count": 3,
      "first_merged_pr": {
        "number": 1,
        "title": "Fix typo in README",
        "url": "https://github.com/owner/repo/pull/1",
        "merged_at": "2024-01-01T00:00:00Z"
      },
      "latest_merged_pr": {
        "number": 9,
        "title": "Add Spanish translation",
        "url": "https://github.com/owner/repo/pull/9",
        "merged_at": "2025-01-01T00:00:00Z"
      },
      "pull_requests_url": "https://github.com/owner/repo/pulls?q=is%3Apr+author%3Awoody"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `login` | GitHub login of the pull request author |
| `profile_url` | `https://github.com/<login>` |
| `merged_pr_count` | Number of that author's pull requests that were merged |
| `first_merged_pr` | The author's earliest merged pull request (by `merged_at`) |
| `latest_merged_pr` | The author's most recent merged pull request (by `merged_at`) |
| `pull_requests_url` | The repository's pull request list filtered to that author |

## Methodology

- **Source:** GitHub pull request data only, from `GET /repos/{owner}/{repo}/pulls?state=closed`, fetched with `gh api --paginate` so the full history is read regardless of size, 100 pull requests per page.
- **Merged:** a pull request counts if `merged_at` is set. Closed-but-unmerged pull requests are ignored.
- **Contributor:** the pull request author (`user.login`). Commits, commit emails, merge commits and `Co-authored-by` trailers aren't used.
- **First / most recent:** the merged pull requests with the earliest and latest `merged_at`. If two were merged in the same second, the lower number counts as earlier.
- **Bots:** authors whose GitHub account type is `Bot` (for example `dependabot[bot]`) are left out. No other filtering is done.
- **Deleted accounts:** GitHub shows pull requests from deleted accounts as authored by its placeholder account [`ghost`](https://github.com/ghost). These pull requests are left out, so they don't merge into a single fake contributor.
- **Order:** contributors are sorted by the date of their first merged pull request, oldest first, then by login.
- **Read-only:** the only request made is the `GET` above, using your existing `gh` login.
- **Reproducible:** the output contains nothing run-specific (no timestamps), and records and keys are always in the same order, so the same version of the tool run against the same repository state gives byte-identical output. The output changes when the repository does: newly merged pull requests, edited pull request titles, and renamed or deleted accounts.

## Tests

```bash
python3 -m unittest -v
```

The tests use small inline fixtures and don't touch the network.
