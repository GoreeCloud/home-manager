"""Source-only security/scope assertions for GC UI synthetic hosted Chrome CI."""

from __future__ import annotations

from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/home-manager-import-checks.yml"


def scoped_job()->str:
    content=WORKFLOW.read_text(encoding="utf-8")
    scope=content.split("  gc-ui-home-manager-preview:\n")
    if len(scope)!=2:
        raise ValueError("missing or duplicated GC UI preview job")
    return scope[1]


class GCUIHostedMainPreviewScopeTests(unittest.TestCase):
    def test_exact_main_branch_push_and_explicit_first_party_review_only(self):
        job=scoped_job()
        self.assertIn("(github.event_name == 'push' && github.ref == 'refs/heads/main')",job)
        self.assertIn("github.event.pull_request.head.repo.full_name == 'GoreeCloud/home-manager'",job)
        self.assertIn("github.head_ref == 'ci/gc-ui-main-browser-gate-20261108'",job)
        self.assertNotIn("github.event_name == 'pull_request' ||",job)

    def test_downloads_only_exact_pinned_public_gc_ui_asset(self):
        job=scoped_job()
        self.assertIn("goreecloud-gc-ui-1.0.1.tgz",job)
        self.assertIn("tools/check_gc_ui_foundations_asset.py",job)
        self.assertIn("tools/stage_gc_ui_home_manager_preview.py",job)
        self.assertIn("persist-credentials: false",job)
        self.assertNotIn("npm install",job)
        self.assertNotIn("npm run",job)

    def test_real_loopback_chrome_smoke_and_short_lived_fake_only_screenshots(self):
        job=scoped_job()
        self.assertIn("127.0.0.1:4173/ui_preview/",job)
        self.assertIn("data-gc-ui-layout-test",job)
        self.assertIn("data-gc-ui-test",job)
        self.assertIn("retention-days: 2",job)
        self.assertIn("home-manager-gc-ui-concept-screenshots",job)
        self.assertNotIn("secrets.",job)
        for command in ("npm publish", "docker push", "kubectl apply",
                        "gh release create", "terraform apply",
                        "aws s3 sync", "rsync --delete"):
            with self.subTest(command=command):
                self.assertNotIn(command, job.lower())

    def test_no_runtime_ui_network_permissions_in_preview_html(self):
        html=(ROOT/"ui_preview/index.html").read_text(encoding="utf-8")
        self.assertIn("connect-src 'none'",html)
        self.assertIn("default-src 'none'",html)
        self.assertIn("Everything shown is synthetic",html)


if __name__=="__main__":
    unittest.main()
