#!/usr/bin/env python3
"""List the merged pull request authors of a GitHub repository as JSON."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from urllib.parse import quote_plus

REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
JQ_FILTER = ".[] | {number, title, html_url, merged_at, login: .user.login, type: .user.type}"


class GhError(Exception):
    pass


def fetch_pull_requests(repo: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["gh", "api", "--paginate", f"repos/{repo}/pulls?state=closed&per_page=100", "--jq", JQ_FILTER],
            stdout=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError:
        raise GhError("gh (GitHub CLI) not found, see https://cli.github.com") from None
    if result.returncode != 0:
        raise GhError(f"gh exited with status {result.returncode}")
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def _summarize(pull_request: dict) -> dict:
    return {
        "number": pull_request["number"],
        "title": pull_request["title"],
        "url": pull_request["html_url"],
        "merged_at": pull_request["merged_at"],
    }


def build_report(repo: str, pull_requests: list[dict]) -> dict:
    by_author: dict[str, list[dict]] = {}
    for pull_request in pull_requests:
        if pull_request["merged_at"] and pull_request["login"] and pull_request["type"] != "Bot":
            by_author.setdefault(pull_request["login"], []).append(pull_request)

    contributors = []
    for login, merged in by_author.items():
        merged.sort(key=lambda pull_request: (pull_request["merged_at"], pull_request["number"]))
        contributors.append({
            "login": login,
            "profile_url": f"https://github.com/{login}",
            "merged_pr_count": len(merged),
            "first_merged_pr": _summarize(merged[0]),
            "latest_merged_pr": _summarize(merged[-1]),
            "pull_requests_url": f"https://github.com/{repo}/pulls?q=" + quote_plus(f"is:pr author:{login}"),
        })

    contributors.sort(key=lambda contributor: (contributor["first_merged_pr"]["merged_at"], contributor["login"]))
    return {"repository": repo, "contributors": contributors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List the merged pull request authors of a GitHub repository as JSON.")
    parser.add_argument("repository", help="GitHub repository as owner/repo, e.g. LibreSign/libresign")
    args = parser.parse_args(argv)
    if not REPOSITORY_PATTERN.fullmatch(args.repository):
        parser.error("repository must look like owner/repo")

    try:
        pull_requests = fetch_pull_requests(args.repository)
    except GhError as error:
        print(f"contribreport: {error}", file=sys.stderr)
        return 1

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stdout.write(json.dumps(build_report(args.repository, pull_requests), indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
