#!/usr/bin/env python3
"""산출물 서버가 지키는 것.

서버는 이제 화면을 그리지 않는다. 뿌리를 열면 **GT 정정 후보로 곧장 보낸다.**
전에는 홈에 카드 넷이 있었는데 그 화면이 스스로 문제를 만들었다 — 「GT 정정 후보」와
「의심되는 GT 찾기」가 같은 상품을 담고 있었는데 카드 문구는 다른 묶음처럼 말했고,
「재판독 판정」은 위 둘과 한 건도 겹치지 않으면서 «위 보고서»를 가리켰다.

그리고 문을 하나 냈다 — 승인. 읽는 자리와 답하는 자리가 갈려 있는 동안 답은 안 쌓였다.
쓰는 자리가 생겼으니 **무엇까지만 쓰는가**가 새로 지킬 선이다.

여기서 지키는 것은 다섯이다.

1. **뿌리는 선언된 산출물로 보낸다.** 파일 이름이 아니라 `artifacts`의 키로만 찾는다.
2. **숫자를 만들지 않는다.** 그릴 화면이 없으므로 셀 자리도 없어야 한다(프로젝트 규칙 8).
3. **속성을 모른다.** 가짜 속성 하나로도 같은 답이 나와야 한다.
4. **원장 말고는 아무것도 쓰지 않는다.** 산출물을 서버가 고치면 원본이 흐려진다.
5. **승인 규격을 서버가 정하지 않는다.** 터미널과 버튼이 같은 검사를 받아야 원장이 한 벌이다.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()
OS_ROOT = PROJECT_ROOT / ".claude/os"
SERVE = OS_ROOT / "engine/scripts/serve_reports.py"


def module():
    sys.path.insert(0, str(OS_ROOT / "engine/scripts"))
    try:
        return __import__("serve_reports")
    finally:
        sys.path.pop(0)


def fake_attribute(root: Path, *, artifacts: dict[str, str] | None = None):
    """엔진이 이름을 모르는 속성 하나. 서버가 특정 속성을 알면 «속성을 지워도 돈다»가 깨진다."""
    run = root / "run"
    (run / "reports").mkdir(parents=True)
    (run / "reports/one.html").write_text("<!doctype html><p>보고서</p>", encoding="utf-8")
    declared = artifacts if artifacts is not None else {
        "gtFixesReport": str(run / "reports/one.html")
    }
    (run / "run-summary.json").write_text(
        json.dumps({"profileId": "widget-finish", "artifacts": declared}), encoding="utf-8"
    )
    profile = root / "profile.json"
    profile.write_text(
        json.dumps({
            "schemaVersion": "catalog-data-profile-v1",
            "id": "widget-finish", "displayName": "표면 처리 감사",
            "attributeName": "표면 처리", "subjectName": "부품", "outputRoot": str(run),
        }),
        encoding="utf-8",
    )
    return module().Attribute(profile)


class LandingTest(unittest.TestCase):
    def test_the_root_points_at_the_declared_gt_fix_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            srv = module()
            attribute = fake_attribute(Path(tmp))
            location = srv.artifact_location(attribute, srv.LANDING_ARTIFACT)
            # 산출물 폴더 안의 상대 주소여야 형제 보고서 링크가 그대로 산다.
            self.assertEqual(location, "/f/widget-finish/reports/one.html")

    def test_an_undeclared_artifact_is_not_guessed(self) -> None:
        """선언에 없으면 없는 것으로 둔다. 경로를 관습으로 추측하면 조용히 옛 파일을 연다."""
        with tempfile.TemporaryDirectory() as tmp:
            srv = module()
            attribute = fake_attribute(Path(tmp), artifacts={})
            self.assertIsNone(srv.artifact_location(attribute, srv.LANDING_ARTIFACT))

    def test_the_landing_key_is_an_artifact_name_not_a_file_name(self) -> None:
        """파일 이름을 적으면 렌더러가 이름을 바꿀 때 조용히 끊긴다."""
        srv = module()
        self.assertNotIn(".html", srv.LANDING_ARTIFACT)


class EngineNeverInventsACountTest(unittest.TestCase):
    """세는 일은 보고서의 몫이다. 서버가 따로 세면 보고서와 조용히 어긋난다."""

    def test_no_queue_recount_in_the_server(self) -> None:
        body = SERVE.read_text(encoding="utf-8")
        for forbidden in ('/ "queue"', "'queue'", '"queue"', "len(rows)", "decidableNow"):
            self.assertNotIn(forbidden, body, f"서버가 셉니다({forbidden}).")

    def test_the_server_renders_no_screen_of_its_own(self) -> None:
        """화면을 그리지 않으면 보고서와 어긋날 자리 자체가 없다."""
        body = SERVE.read_text(encoding="utf-8")
        for gone in ("def page_", "STYLE = ", "def render_markdown", "def top_bar"):
            self.assertNotIn(gone, body, f"화면을 그리는 코드가 남아 있습니다: {gone}")


class ApprovalDoorTest(unittest.TestCase):
    """쓰는 자리는 하나다 — 승인.

    전에는 서버가 아무것도 쓰지 않았고, 그래서 보고서가 「이 GT를 고치자」고 열 건을
    늘어놔도 사람은 그 화면에서 답할 수 없었다. **읽는 자리와 답하는 자리가 갈리면
    답은 안 쌓인다.** 문을 하나 냈으니 그 문턱을 여기서 지킨다.
    """

    def submission(self, headers: dict[str, str], body: bytes = b"{}"):
        srv = module()
        handler = srv.Handler.__new__(srv.Handler)
        handler.headers = headers
        handler.rfile = io.BytesIO(body)
        return handler.read_submission()

    def test_only_a_json_body_gets_through(self) -> None:
        """다른 페이지가 몰래 만든 평범한 폼은 JSON을 보낼 수 없다. 그 선이 유일한 문턱이다."""
        srv = module()
        with self.assertRaises(srv.DecisionRejected):
            self.submission({"Content-Type": "application/x-www-form-urlencoded",
                             "Content-Length": "2"})

    def test_a_request_from_another_origin_is_refused(self) -> None:
        srv = module()
        with self.assertRaises(srv.DecisionRejected):
            self.submission({"Content-Type": "application/json", "Content-Length": "2",
                             "Origin": "https://evil.example"})

    def test_a_local_json_submission_is_read(self) -> None:
        body = b'{"productKey":"P1"}'
        value = self.submission(
            {"Content-Type": "application/json", "Content-Length": str(len(body)),
             "Origin": "http://127.0.0.1:7391"},
            body,
        )
        self.assertEqual(value["productKey"], "P1")

    def test_an_oversized_body_is_not_read(self) -> None:
        srv = module()
        with self.assertRaises(srv.DecisionRejected):
            self.submission({"Content-Type": "application/json",
                             "Content-Length": str(srv.MAX_BODY + 1)})

    def test_the_server_does_not_define_the_approval_contract(self) -> None:
        """규격이 두 벌이면 터미널로 온 판정과 버튼으로 온 판정이 다른 검사를 받는다."""
        srv = module()
        sys.path.insert(0, str(OS_ROOT / "engine/scripts"))
        try:
            recorder = __import__("record_review_decision")
        finally:
            sys.path.pop(0)
        self.assertIs(srv.record, recorder.record)

    def test_the_server_writes_nothing_but_the_ledger(self) -> None:
        """산출물을 서버가 고치면, 다음 사람은 어느 파일이 사이클의 것인지 알 수 없다."""
        body = SERVE.read_text(encoding="utf-8")
        for forbidden in ("write_text", "write_bytes", "mkdir", "unlink"):
            self.assertNotIn(forbidden, body, f"서버가 파일을 씁니다({forbidden}).")


class ProcessTest(unittest.TestCase):
    """레포 맨 위의 serve.sh가 «두 번 눌러도 하나»를 지키는지, 뿌리가 어디로 보내는지 본다."""

    def test_start_is_idempotent_and_the_root_redirects(self) -> None:
        serve = PROJECT_ROOT / "serve.sh"
        port = "7519"
        env = {"CATALOG_OS_PORT": port, "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [str(serve), *args], capture_output=True, text=True, env=env, timeout=30
            )

        run("stop")
        try:
            first = run("start")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("이미 떠 있습니다", run("start").stdout)
            self.assertEqual(run("status").returncode, 0)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=5) as response:
                self.assertEqual(response.read().strip(), b"ok")

            # 뿌리는 스스로 그리지 않고 보고서로 보낸다. 따라간 끝이 GT 정정 후보여야 한다.
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003
                    return None

            opener = urllib.request.build_opener(NoRedirect)
            try:
                opener.open(f"http://127.0.0.1:{port}/", timeout=5)
                self.fail("뿌리가 리다이렉트하지 않았습니다.")
            except urllib.error.HTTPError as error:
                self.assertEqual(error.code, 302)
                self.assertIn("gt-fixes.html", error.headers["Location"])
        finally:
            run("stop")


if __name__ == "__main__":
    unittest.main()
