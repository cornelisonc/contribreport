import random
import unittest

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

    def test_no_merged_prs_gives_empty_contributors(self):
        report = contribreport.build_report("owner/repo", [pr(1, "woody", None)])

        self.assertEqual(report, {"repository": "owner/repo", "contributors": []})


if __name__ == "__main__":
    unittest.main()
