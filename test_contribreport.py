import io
import json
import random
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import contribreport


def pr(number, login, merged_at, type="User", title=None):
    return {
        "number": number,
        "title": title if title is not None else f"PR {number}",
        "html_url": f"https://github.com/owner/repo/pull/{number}",
        "merged_at": merged_at,
        "login": login,
        "type": type,
    }


def logins(report):
    return [contributor["login"] for contributor in report["contributors"]]


class BuildReportTest(unittest.TestCase):
    def test_excludes_unmerged_pull_requests(self):
        report = contribreport.build_report("owner/repo", [
            pr(1, "woody", None),
            pr(2, "buzz", "2024-01-01T00:00:00Z"),
        ])

        self.assertEqual(logins(report), ["buzz"])

    def test_groups_by_login_and_counts(self):
        report = contribreport.build_report("owner/repo", [
            pr(1, "woody", "2024-01-01T00:00:00Z"),
            pr(2, "buzz", "2024-01-02T00:00:00Z"),
            pr(3, "woody", "2024-01-03T00:00:00Z"),
            pr(4, "woody", None),
        ])

        counts = {c["login"]: c["merged_pr_count"] for c in report["contributors"]}
        self.assertEqual(counts, {"woody": 2, "buzz": 1})

    def test_first_and_latest_follow_merged_at_not_number_or_input_order(self):
        report = contribreport.build_report("owner/repo", [
            pr(10, "woody", "2024-06-01T00:00:00Z"),
            pr(30, "woody", "2024-03-01T00:00:00Z"),
            pr(50, "woody", "2024-01-01T00:00:00Z"),
        ])

        woody = report["contributors"][0]
        self.assertEqual(woody["first_merged_pr"]["number"], 50)
        self.assertEqual(woody["latest_merged_pr"]["number"], 10)

    def test_merged_at_tie_is_broken_by_number(self):
        report = contribreport.build_report("owner/repo", [
            pr(7, "woody", "2024-01-01T00:00:00Z"),
            pr(3, "woody", "2024-01-01T00:00:00Z"),
            pr(5, "woody", "2024-01-01T00:00:00Z"),
        ])

        woody = report["contributors"][0]
        self.assertEqual(woody["first_merged_pr"]["number"], 3)
        self.assertEqual(woody["latest_merged_pr"]["number"], 7)

    def test_excludes_bots_and_pull_requests_without_author(self):
        report = contribreport.build_report("owner/repo", [
            pr(1, "dependabot[bot]", "2024-01-01T00:00:00Z", type="Bot"),
            pr(2, None, "2024-01-02T00:00:00Z", type=None),
            pr(3, "woody", "2024-01-03T00:00:00Z"),
        ])

        self.assertEqual(logins(report), ["woody"])

    def test_sorts_by_first_merge_then_login(self):
        report = contribreport.build_report("owner/repo", [
            pr(1, "jessie", "2024-03-01T00:00:00Z"),
            pr(2, "buzz", "2024-01-01T00:00:00Z"),
            pr(3, "woody", "2024-01-01T00:00:00Z"),
            pr(4, "woody", "2023-12-31T00:00:00Z"),
            pr(5, "buzz", "2025-01-01T00:00:00Z"),
        ])

        self.assertEqual(logins(report), ["woody", "buzz", "jessie"])

    def test_record_fields_and_urls(self):
        report = contribreport.build_report("owner/repo", [
            pr(2, "woody", "2024-05-01T00:00:00Z", title="Second"),
            pr(1, "woody", "2024-01-01T00:00:00Z", title="First"),
        ])

        self.assertEqual(report, {
            "repository": "owner/repo",
            "contributors": [
                {
                    "login": "woody",
                    "profile_url": "https://github.com/woody",
                    "merged_pr_count": 2,
                    "first_merged_pr": {
                        "number": 1,
                        "title": "First",
                        "url": "https://github.com/owner/repo/pull/1",
                        "merged_at": "2024-01-01T00:00:00Z",
                    },
                    "latest_merged_pr": {
                        "number": 2,
                        "title": "Second",
                        "url": "https://github.com/owner/repo/pull/2",
                        "merged_at": "2024-05-01T00:00:00Z",
                    },
                    "pull_requests_url": "https://github.com/owner/repo/pulls?q=is%3Apr+author%3Awoody",
                },
            ],
        })
        self.assertEqual(
            list(report["contributors"][0]),
            ["login", "profile_url", "merged_pr_count", "first_merged_pr", "latest_merged_pr", "pull_requests_url"],
        )

    def test_shuffled_input_gives_identical_output(self):
        pull_requests = [
            pr(n, login, f"2024-01-{day:02d}T00:00:00Z")
            for n, (login, day) in enumerate(
                [("woody", 3), ("buzz", 1), ("woody", 1), ("jessie", 2), ("buzz", 3), ("woody", 3)],
                start=1,
            )
        ]
        expected = contribreport.build_report("owner/repo", pull_requests)

        shuffled = list(pull_requests)
        random.Random(42).shuffle(shuffled)

        self.assertEqual(contribreport.build_report("owner/repo", shuffled), expected)

    def test_excludes_ghost_placeholder_for_deleted_accounts(self):
        report = contribreport.build_report("owner/repo", [
            pr(1, "ghost", "2024-01-01T00:00:00Z"),
            pr(2, "ghost", "2024-01-02T00:00:00Z"),
            pr(3, "woody", "2024-01-03T00:00:00Z"),
        ])

        self.assertEqual(logins(report), ["woody"])

    def test_no_merged_prs_gives_empty_contributors(self):
        report = contribreport.build_report("owner/repo", [pr(1, "woody", None)])

        self.assertEqual(report, {"repository": "owner/repo", "contributors": []})


def completed(stdout="", returncode=0):
    return subprocess.CompletedProcess(args=["gh"], returncode=returncode, stdout=stdout)


class FetchPullRequestsTest(unittest.TestCase):
    @mock.patch("contribreport.subprocess.run")
    def test_fetch_paginates_closed_pulls_and_parses_each_line(self, run):
        run.return_value = completed(
            json.dumps(pr(1, "woody", "2024-01-01T00:00:00Z")) + "\n"
            + json.dumps(pr(2, "buzz", None)) + "\n"
        )

        pull_requests = contribreport.fetch_pull_requests("owner/repo")

        self.assertEqual(pull_requests, [pr(1, "woody", "2024-01-01T00:00:00Z"), pr(2, "buzz", None)])
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["gh", "api", "--paginate", "repos/owner/repo/pulls?state=closed&per_page=100"])
        self.assertEqual(command[4], "--jq")

    @mock.patch("contribreport.subprocess.run")
    def test_fetch_skips_blank_lines(self, run):
        run.return_value = completed("\n\n")

        self.assertEqual(contribreport.fetch_pull_requests("owner/repo"), [])

    @mock.patch("contribreport.subprocess.run")
    def test_fetch_raises_when_gh_fails(self, run):
        run.return_value = completed(json.dumps(pr(1, "woody", "2024-01-01T00:00:00Z")) + "\n", returncode=1)

        with self.assertRaises(contribreport.GhError):
            contribreport.fetch_pull_requests("owner/repo")

    @mock.patch("contribreport.subprocess.run", side_effect=FileNotFoundError)
    def test_fetch_raises_when_gh_is_missing(self, run):
        with self.assertRaisesRegex(contribreport.GhError, "https://cli.github.com"):
            contribreport.fetch_pull_requests("owner/repo")


class MainTest(unittest.TestCase):
    def run_main(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = contribreport.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    @mock.patch("contribreport.fetch_pull_requests")
    def test_main_prints_report_as_json(self, fetch):
        pull_requests = [pr(1, "woody", "2024-01-01T00:00:00Z"), pr(2, "buzz", "2024-02-01T00:00:00Z")]
        fetch.return_value = pull_requests

        code, stdout, _ = self.run_main(["owner/repo"])

        self.assertEqual(code, 0)
        fetch.assert_called_once_with("owner/repo")
        self.assertEqual(json.loads(stdout), contribreport.build_report("owner/repo", pull_requests))
        self.assertTrue(stdout.endswith("}\n"))

    @mock.patch("contribreport.fetch_pull_requests")
    def test_main_keeps_non_ascii_titles_readable(self, fetch):
        fetch.return_value = [pr(1, "woody", "2024-01-01T00:00:00Z", title='Corrige "ação" 🎉')]

        _, stdout, _ = self.run_main(["owner/repo"])

        self.assertIn('Corrige \\"ação\\" 🎉', stdout)

    @mock.patch("contribreport.fetch_pull_requests", side_effect=contribreport.GhError("gh exited with status 1"))
    def test_main_prints_nothing_and_returns_1_when_gh_fails(self, fetch):
        code, stdout, stderr = self.run_main(["owner/repo"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("gh exited with status 1", stderr)

    @mock.patch("contribreport.fetch_pull_requests")
    def test_main_rejects_malformed_repository(self, fetch):
        for repository in ["owner", "owner/repo/", "https://github.com/owner/repo", "owner/repo\n"]:
            with self.subTest(repository=repository):
                with self.assertRaises(SystemExit) as raised:
                    self.run_main([repository])
                self.assertEqual(raised.exception.code, 2)
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
