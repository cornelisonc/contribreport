#!/usr/bin/env python3
"""List the merged pull request authors of a GitHub repository as JSON."""

from __future__ import annotations

from urllib.parse import quote_plus


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
