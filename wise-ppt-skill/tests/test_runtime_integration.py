from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT = REPO_ROOT / "runtime" / "screenshot.sh"
PAPER_ASSETS = REPO_ROOT / "themes" / "paper-ink" / "assets"
D6_PAGE = REPO_ROOT / "themes" / "paper-ink" / "gallery" / "ai" / "frames" / "layout-d6.html"
QR_PAYLOAD = "http://weixin.qq.com/r/mp/sDgNFUrEMRdOrQ52922i"


def find_chrome() -> str | None:
    mac_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if mac_chrome.is_file() and os.access(mac_chrome, os.X_OK):
        return str(mac_chrome)
    for name in ("google-chrome", "chrome", "chromium"):
        executable = shutil.which(name)
        if executable:
            return executable
    return None


CHROME = find_chrome()


def run_command(args: list[str], *, timeout: float = 45) -> subprocess.CompletedProcess[str]:
    """Run a browser integration command and terminate its whole process group on timeout."""

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["WISE_PPT_WAIT_STEPS"] = "160"
    process = subprocess.Popen(
        args,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        raise AssertionError(
            f"command timed out after {timeout}s: {args!r}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def balance_page(
    *,
    mode: str,
    body_markup: str,
    include_frame: bool = True,
) -> str:
    figure = ""
    caption = ""
    if include_frame:
        figure = """
      <text x="200" y="176">FIG. TEST — BALANCE</text>
      <line x1="200" y1="192" x2="520" y2="192" stroke="#191917" />
"""
        caption = '<div class="caption">Balance integration fixture.</div>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <link rel="stylesheet" href="../assets/shared.css">
  <style>
    svg.scene {{ position:absolute; inset:0; z-index:1; }}
    .caption {{
      position:absolute; left:0; right:0; bottom:118px;
      text-align:center; font-size:33px; line-height:1.2;
    }}
  </style>
</head>
<body>
  <div class="stage">
    <svg class="scene" width="1920" height="1080" viewBox="0 0 1920 1080">
{figure}      <g id="body" data-balance="{mode}">
{body_markup}
      </g>
    </svg>
    {caption}
  </div>
  <script src="../assets/particles.js"></script>
  <script>stageFit();</script>
</body>
</html>
"""


@unittest.skipUnless(CHROME, "Chrome/Chromium is required for runtime integration tests")
class RuntimeIntegrationTests(unittest.TestCase):
    maxDiff = None

    def run_balance(self, html: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="wise-ppt-balance-test-") as temporary:
            root = Path(temporary)
            deck = root / "deck"
            frames = deck / "frames"
            frames.mkdir(parents=True)
            (deck / "assets").symlink_to(PAPER_ASSETS, target_is_directory=True)
            (frames / "shot-01.html").write_text(html, encoding="utf-8")
            return run_command(
                ["bash", str(SCREENSHOT), str(deck), str(root / "out"), "", "audit"]
            )

    def assert_audit_failure(self, html: str, expected_status: str) -> None:
        result = self.run_balance(html)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(expected_status, output)

    def test_centered_pass_and_excluded_decoration(self) -> None:
        result = self.run_balance(
            balance_page(
                mode="centered",
                body_markup="""
        <rect x="860" y="455" width="200" height="200" fill="#191917" />
        <g data-balance-exclude="true">
          <rect x="0" y="0" width="1920" height="1080" fill="#191917" />
        </g>""",
            )
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("pass", output)
        self.assertIn("dx=0", output)
        self.assertIn("dy=0", output)
        self.assertIn("overflow=0,0,0,0", output)

    def test_centered_offset_fails(self) -> None:
        self.assert_audit_failure(
            balance_page(
                mode="centered",
                body_markup='<rect x="700" y="455" width="200" height="200" />',
            ),
            "fail-center",
        )

    def test_empty_body_fails(self) -> None:
        self.assert_audit_failure(
            balance_page(mode="centered", body_markup=""),
            "error-empty-body",
        )

    def test_missing_frame_fails(self) -> None:
        self.assert_audit_failure(
            balance_page(
                mode="centered",
                body_markup='<rect x="860" y="455" width="200" height="200" />',
                include_frame=False,
            ),
            "error-missing-frame",
        )

    def test_invalid_mode_fails(self) -> None:
        self.assert_audit_failure(
            balance_page(
                mode="centred",
                body_markup='<rect x="860" y="455" width="200" height="200" />',
            ),
            "error-invalid-mode",
        )

    def test_structural_overflow_fails(self) -> None:
        self.assert_audit_failure(
            balance_page(
                mode="structural",
                body_markup='<rect x="100" y="455" width="200" height="200" />',
            ),
            "fail-overflow",
        )

    def test_d6_qr_expected_payload_passes_and_wrong_payload_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wise-ppt-qr-test-") as temporary:
            root = Path(temporary)
            theme = root / "theme"
            deck = theme / "gallery" / "ai"
            frames = deck / "frames"
            frames.mkdir(parents=True)
            (theme / "assets").symlink_to(PAPER_ASSETS, target_is_directory=True)
            page = frames / "layout-d6.html"
            original = D6_PAGE.read_text(encoding="utf-8")
            page.write_text(original, encoding="utf-8")

            positive = run_command(
                ["bash", str(SCREENSHOT), str(deck), str(root / "positive")],
                timeout=60,
            )
            positive_output = positive.stdout + positive.stderr
            self.assertEqual(positive.returncode, 0, positive_output)
            self.assertIn(f"PASS QR {root / 'positive' / 'layout-d6.png'}: {QR_PAYLOAD}", positive_output)

            wrong_payload = "https://example.invalid/wrong-qr-payload"
            marker = f"var QR_PAYLOAD = '{QR_PAYLOAD}';"
            self.assertIn(marker, original)
            page.write_text(
                original.replace(marker, f"var QR_PAYLOAD = '{wrong_payload}';", 1),
                encoding="utf-8",
            )
            negative = run_command(
                ["bash", str(SCREENSHOT), str(deck), str(root / "negative")],
                timeout=60,
            )
            negative_output = negative.stdout + negative.stderr
            self.assertNotEqual(negative.returncode, 0, negative_output)
            self.assertIn("FAIL QR", negative_output)
            self.assertIn(f"expected {wrong_payload!r}", negative_output)
            self.assertIn(QR_PAYLOAD, negative_output)


if __name__ == "__main__":
    unittest.main()
