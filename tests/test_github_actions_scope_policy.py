from __future__ import annotations

import unittest
from unittest import mock

from security_lab.platform import github_actions


class GitHubActionsScopePolicyTests(unittest.TestCase):
    def test_runtime_auth_accepts_repo_without_workflow_scope(self) -> None:
        result = {
            "returncode": 0,
            "stdout": "",
            "stderr": "Logged in to github.com\n  - Token scopes: 'codespace', 'gist', 'read:org', 'repo'\n",
        }
        with mock.patch.object(github_actions, "_gh", return_value=result):
            status = github_actions.auth_status()

        self.assertTrue(status["authenticated"])
        self.assertTrue(status["safe"])
        self.assertEqual(status["missing_scopes"], [])
        self.assertEqual(status["unexpected_scopes"], [])

    def test_publish_auth_still_requires_workflow_scope(self) -> None:
        result = {
            "returncode": 0,
            "stdout": "",
            "stderr": "Logged in to github.com\n  - Token scopes: 'codespace', 'repo'\n",
        }
        with mock.patch.object(github_actions, "_gh", return_value=result):
            status = github_actions.auth_status(github_actions.PUBLISH_REQUIRED_SCOPES)

        self.assertTrue(status["authenticated"])
        self.assertFalse(status["safe"])
        self.assertEqual(status["missing_scopes"], ["workflow"])
        self.assertEqual(status["unexpected_scopes"], [])


if __name__ == "__main__":
    unittest.main()
