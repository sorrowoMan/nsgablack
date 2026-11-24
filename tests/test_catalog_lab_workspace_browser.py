"""Opt-in browser regression over a private, banner-free workspace fixture.

Run explicitly with NSGABLACK_RUN_WORKSPACE_BROWSER_TESTS=1. This test never
opens a user's browser/profile or reads the operator's workspace credentials.
The spawned Streamlit process and Chromium contexts belong only to this test.
"""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("NSGABLACK_RUN_WORKSPACE_BROWSER_TESTS") != "1",
    reason="Set NSGABLACK_RUN_WORKSPACE_BROWSER_TESTS=1 for the isolated browser regression",
)

REPO = Path(__file__).resolve().parents[1]
_CREDENTIAL_ENV = (
    "NSGABLACK_PROJECT_WORKSPACE_CLIENT_CONFIG", "NSGABLACK_PROJECT_WORKSPACE_ROOT",
    "NSGABLACK_PROJECT_WORKSPACE_SOURCES", "NSGABLACK_LAB_CLIENT_CONFIG",
    "NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG", "NSGABLACK_PROJECT_RESULT_CLIENT_CONFIG",
    "NSGABLACK_CATALOG_AI_CONFIG", "NSGABLACK_CATALOG_READER_CONFIG",
    "NSGABLACK_CATALOG_WRITER_CONFIG", "NSGABLACK_CATALOG_HOSTED",
    "NSGABLACK_WORKSPACE_PLAINTEXT_EDITOR",
)


def _fixture_source(*, remove_header_guard: bool = False) -> str:
    """No leading caption: the toolbar must occupy the production position.

    ``remove_header_guard`` is a diagnostic negative control for temporary
    fixtures only. It never modifies the repository stylesheet.
    """
    header_control = ""
    if remove_header_guard:
        header_control = '''
from nsgablack.catalog import lab_workspace_style
_styles = lab_workspace_style.workspace_styles
def without_header_guard(theme="dark"):
    return _styles(theme).replace(
        'header[data-testid="stHeader"]{pointer-events:none!important;}', ''
    ).replace(
        'header[data-testid="stHeader"] button,header[data-testid="stHeader"] [role="button"]{pointer-events:auto;}', ''
    )
lab_workspace_style.workspace_styles = without_header_guard
'''
    return f'''from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys
import streamlit as st

REPO = Path({str(REPO)!r})
sys.path.insert(0, str(REPO.parent))
spec = importlib.util.spec_from_file_location("workspace_browser_fakes", REPO / "tests/test_catalog_lab_workspace_ui.py")
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)

from nsgablack.catalog import lab_workspace_ui as ui
from nsgablack.catalog import lab_workspace_reference as reference
from nsgablack.catalog.lab_workspace_transport import WorkspaceRPCClient
from nsgablack.catalog.curation_provider import DeepSeekGenerator

def forbidden(*args, **kwargs):
    raise AssertionError("Browser fixture cannot call real RPC or a paid model")
WorkspaceRPCClient.call = forbidden
for name in ("generate", "review", "_complete"):
    setattr(DeepSeekGenerator, name, forbidden)

st.set_page_config(layout="wide", initial_sidebar_state="expanded")
if "browser_fake_runtime" not in st.session_state:
    st.session_state.browser_fake_runtime = SimpleNamespace(
        store=fakes.FakeStore(), runner=fakes.FakeRunner())

source = reference.ReferenceSource([
    {{"key":"adapter.alpha", "title":"AlphaAdapter", "kind":"adapter",
      "summary":"Alpha-only component detail", "minimal_wiring":["alpha = AlphaAdapter()"],
      "companions":["adapter.gamma"]}},
    {{"key":"adapter.beta", "title":"BetaAdapter", "kind":"adapter",
      "summary":"Beta-only component detail", "minimal_wiring":["beta = BetaAdapter()"],
      "companions":["adapter.gamma"]}},
    {{"key":"adapter.gamma", "title":"GammaAdapter", "kind":"adapter",
      "summary":"Gamma-only component detail", "minimal_wiring":["gamma = GammaAdapter()"],
      "companions":["adapter.alpha"]}},
])
reference.reference_source = lambda: source
{header_control}
ui.render_workspace(st, st.session_state.browser_fake_runtime)
'''


def _free_loopback_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _start_fixture(directory: Path, *, remove_header_guard: bool = False):
    """Start a single owned headless process; caller must use _stop_fixture."""
    directory.mkdir(parents=True, exist_ok=True)
    app = directory / "workspace_fixture.py"
    app.write_text(_fixture_source(remove_header_guard=remove_header_guard), encoding="utf-8")
    port = _free_loopback_port()
    environment = {key: value for key, value in os.environ.items() if key not in _CREDENTIAL_ENV}
    environment["PYTHONPATH"] = str(REPO.parent)
    environment["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    log = (directory / "streamlit.log").open("wb")
    command = [
        sys.executable, "-m", "streamlit", "run", str(app),
        "--server.address=127.0.0.1", f"--server.port={port}",
        "--server.headless=true", "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false", "--logger.level=error", "--theme.base=dark",
    ]
    try:
        process = subprocess.Popen(command, cwd=REPO, env=environment,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except BaseException:
        log.close()
        raise
    url = f"http://127.0.0.1:{port}/"
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Owned Streamlit fixture exited ({process.returncode}); see {directory / 'streamlit.log'}")
            try:
                with urlopen(url + "_stcore/health", timeout=.5) as response:
                    if response.status == 200:
                        return process, log, url
            except (OSError, URLError):
                pass
            time.sleep(.1)
        raise RuntimeError("Owned Streamlit fixture did not become healthy in 30 seconds")
    except BaseException:
        _stop_fixture(process, log)
        raise


def _stop_fixture(process, log) -> None:
    # Popen holds the exact child handle. Never kill a port owner or enumerate
    # unrelated Python processes to perform cleanup.
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    finally:
        log.close()


@pytest.fixture
def browser_workspace(tmp_path):
    pytest.importorskip("streamlit")
    process, log, url = _start_fixture(tmp_path)
    try:
        yield url
    finally:
        _stop_fixture(process, log)


@pytest.mark.parametrize("viewport", [(1440, 1000), (1280, 800)])
def test_top_component_lookup_and_dialog_navigation_keep_draft(browser_workspace, tmp_path, viewport):
    """A normal click must reach the toolbar below Streamlit's fixed header."""
    browser_api = pytest.importorskip("playwright.sync_api")
    browser_api.expect.set_options(timeout=15000)
    width, height = viewport
    with browser_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": width, "height": height}, locale="zh-CN")
        context.route("**/*", lambda route: route.continue_()
            if route.request.url.startswith(browser_workspace) else route.abort())
        page = context.new_page()
        page.set_default_timeout(15000)
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        try:
            page.goto(browser_workspace)
            editor_frame = page.frame_locator('iframe[title*="nsgablack_workspace_editor"]')
            editor = editor_frame.locator(".cm-content")
            browser_api.expect(editor).to_contain_text("def build_solver")
            editor.click()
            editor.press("Control+End")
            marker = "# unsaved-browser-regression-marker"
            page.keyboard.insert_text("\n" + marker)
            browser_api.expect(page.get_by_role("button", name="保存", exact=False)).to_be_enabled()

            # Do not force clicks or inject overlays/styles. The original bug
            # was a transparent stHeader that intercepted this real click.
            page.get_by_role("button", name="查组件", exact=False).click()
            dialog = page.get_by_role("dialog")
            browser_api.expect(dialog).to_be_visible()
            browser_api.expect(dialog.get_by_role("heading", name="AlphaAdapter", exact=True)).to_be_visible()
            dialog.get_by_role("button", name="BetaAdapter", exact=True).click()
            browser_api.expect(dialog.get_by_role("heading", name="BetaAdapter", exact=True)).to_be_visible()
            browser_api.expect(dialog.get_by_test_id("stCode").filter(has_text="beta = BetaAdapter()")).to_be_visible()

            dialog.get_by_role("tab", name="相关组件", exact=True).click()
            dialog.get_by_role("tabpanel").get_by_role("button", name="GammaAdapter", exact=True).click()
            browser_api.expect(dialog.get_by_role("heading", name="GammaAdapter", exact=True)).to_be_visible()
            dialog.get_by_role("tab", name="怎么用", exact=True).click()
            browser_api.expect(dialog.get_by_test_id("stCode").filter(has_text="gamma = GammaAdapter()")).to_be_visible()
            dialog.get_by_role("button", name="返回上一组件", exact=True).click()
            browser_api.expect(dialog.get_by_role("heading", name="BetaAdapter", exact=True)).to_be_visible()
            browser_api.expect(dialog.get_by_test_id("stCode").filter(has_text="beta = BetaAdapter()")).to_be_visible()
            dialog.get_by_role("button", name="返回编辑", exact=True).click()
            browser_api.expect(dialog).not_to_be_visible()
            browser_api.expect(editor).to_contain_text(marker)

            page.get_by_role("button", name="查组件", exact=False).click()
            browser_api.expect(dialog).to_be_visible()
            browser_api.expect(dialog.get_by_role("heading", name="BetaAdapter", exact=True)).to_be_visible()
            browser_api.expect(dialog.get_by_test_id("stCode").filter(has_text="beta = BetaAdapter()")).to_be_visible()
            dialog.get_by_role("button", name="返回编辑", exact=True).click()
            browser_api.expect(dialog).not_to_be_visible()
            browser_api.expect(editor).to_contain_text(marker)

            # The empty header is click-through, while its real expand button
            # must remain usable after the sidebar is collapsed.
            page.get_by_test_id("stSidebar").hover()
            page.get_by_test_id("stSidebarCollapseButton").get_by_role("button").click()
            expand = page.get_by_test_id("stExpandSidebarButton")
            browser_api.expect(expand).to_be_visible()
            expand.click()
            browser_api.expect(page.get_by_test_id("stSidebar")).to_have_attribute("aria-expanded", "true")
            browser_api.expect(editor).to_contain_text(marker)
            assert not page_errors
        except BaseException:
            page.screenshot(path=str(tmp_path / f"workspace-browser-failure-{width}x{height}.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()
