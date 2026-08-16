from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from nsgablack.catalog import dashboard_page as page_protocol
from nsgablack.experiment.dashboard import _build_deep_link_query
from nsgablack.plugins import list_runtime_artifact_surfaces

sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright

_EDGE_CANDIDATES = (
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
)
_EDGE_AVAILABLE = any(path.exists() for path in _EDGE_CANDIDATES)
pytestmark = pytest.mark.skipif(
    not _EDGE_AVAILABLE,
    reason="Experiment dashboard E2E requires Microsoft Edge.",
)

_ROOT = Path(__file__).resolve().parents[1]
_SECTION_IDS = (
    page_protocol.HERO_SECTION_ID,
    page_protocol.FILTER_SECTION_ID,
    page_protocol.RESULT_SECTION_ID,
    page_protocol.DETAIL_SECTION_ID,
)


def _prepare_runtime_surface_db(sample_problem, sample_bias, tmp_path: Path) -> tuple[Path, str]:
    from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.plugins import (
        ModuleReportConfig,
        ModuleReportPlugin,
        RuntimeSurfaceTrackerConfig,
        RuntimeSurfaceTrackerPlugin,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-10.0, high=10.0),
        mutator=ContextGaussianMutation(base_sigma=0.5, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-10.0, high=10.0),
    )
    solver = ComposableSolver(
        problem=sample_problem,
        adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=6)),
        representation_pipeline=pipeline,
        bias_module=sample_bias,
    )
    db_path = tmp_path / "runtime_surface.sqlite3"
    solver.add_plugin(
        ModuleReportPlugin(
            config=ModuleReportConfig(
                output_dir=str(tmp_path),
                run_id="runtime_surface_e2e_demo",
                write_bias_markdown=False,
            )
        )
    )
    solver.add_plugin(
        RuntimeSurfaceTrackerPlugin(
            config=RuntimeSurfaceTrackerConfig(
                db_path=str(db_path),
                namespace="ut_runtime_e2e",
                tag="e2e",
            )
        )
    )
    solver.max_steps = 3
    result = solver.run()
    return db_path, str(result.get("run_id") or "")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http_ready(base_url: str, *, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url, timeout=2.0) as response:
                if int(getattr(response, "status", 200)) < 500:
                    return
        except Exception as exc:  # pragma: no cover
            last_error = exc
            time.sleep(0.5)
    raise AssertionError(f"experiment ui did not become reachable: {base_url} ({last_error})")


@contextlib.contextmanager
def _running_experiment_ui(db_path: Path, *extra_args: str):
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    log_file = tempfile.NamedTemporaryFile(prefix="nsgablack_experiment_ui_", suffix=".log", delete=False)
    log_path = Path(log_file.name)
    log_file.close()
    command = [
        sys.executable,
        "-m",
        "nsgablack",
        "experiment",
        "ui",
        "--db",
        str(db_path),
        "--port",
        str(port),
        "--headless",
        *extra_args,
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with log_path.open("w", encoding="utf-8") as handle:
        proc = subprocess.Popen(
            command,
            cwd=_ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy(),
            creationflags=creationflags,
        )
    try:
        _wait_for_http_ready(base_url)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill()
            proc.wait(timeout=10)
        with contextlib.suppress(OSError):
            log_path.unlink()


def _wait_for_sections(page, *, timeout_ms: int = 60000) -> None:
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        if all(page.locator(f"#{section_id}").count() == 1 for section_id in _SECTION_IDS):
            return
        page.wait_for_timeout(500)
    raise AssertionError(f"experiment dashboard did not render expected sections: {_SECTION_IDS}")


def _wait_for_body_text(page, expected: str, *, timeout_ms: int = 60000) -> None:
    deadline = time.time() + (timeout_ms / 1000.0)
    last_text = ""
    while time.time() < deadline:
        page.wait_for_timeout(700)
        last_text = page.locator("body").inner_text()
        if expected in last_text:
            return
    raise AssertionError(f"expected text not found: {expected!r}\nLast body text:\n{last_text[:4000]}")


def _results_expander_is_open(page) -> bool:
    details = page.locator('[data-testid="stExpander"]').first.locator("details").first
    return details.get_attribute("open") is not None


def _wait_for_selected_in_deep_link(page, expected_selected: str, *, timeout_ms: int = 60000) -> str:
    deadline = time.time() + (timeout_ms / 1000.0)
    last_value = ""
    while time.time() < deadline:
        page.wait_for_timeout(700)
        locator = page.get_by_label("Deep-Link / 直达链接")
        if locator.count() != 1:
            continue
        last_value = locator.input_value()
        selected = parse_qs(last_value.lstrip("?")).get("selected", [""])[0]
        if selected == expected_selected:
            return last_value
    raise AssertionError(
        f"deep-link selected did not become {expected_selected!r}\nLast deep-link value: {last_value!r}"
    )


def _wait_for_selected_change_in_deep_link(page, original_selected: str, *, timeout_ms: int = 60000) -> tuple[str, str]:
    deadline = time.time() + (timeout_ms / 1000.0)
    last_value = ""
    while time.time() < deadline:
        page.wait_for_timeout(700)
        locator = page.get_by_label("Deep-Link / 直达链接")
        if locator.count() != 1:
            continue
        last_value = locator.input_value()
        selected = parse_qs(last_value.lstrip("?")).get("selected", [""])[0]
        if selected and selected != original_selected:
            return selected, last_value
    next_link = page.get_by_role("link", name="下一项链接 / Next Link")
    raise AssertionError(
        f"deep-link selected did not change away from {original_selected!r}"
        f"\nPage URL: {page.url!r}"
        f"\nNext-link href: {next_link.get_attribute('href') if next_link.count() == 1 else None!r}"
        f"\nNext-link target: {next_link.get_attribute('target') if next_link.count() == 1 else None!r}"
        f"\nLast deep-link value: {last_value!r}"
    )


def test_experiment_dashboard_deep_link_roundtrip_e2e(sample_problem, sample_bias, tmp_path: Path):
    db_path, run_id = _prepare_runtime_surface_db(sample_problem, sample_bias, tmp_path)
    artifact_rows = list_runtime_artifact_surfaces(db_path, artifact_role="report", limit=20)
    assert len(artifact_rows) >= 2
    first_key = f"artifact:{run_id}:{artifact_rows[0]['artifact_id']}"

    initial_query = _build_deep_link_query(
        base_params={
            "db": str(db_path),
            "limit": "200",
            "view": "artifact_catalog",
            "selected": first_key,
            "detail_tab": "contracts",
            "column_mode": "full",
            "page_size": "20",
            "results_collapse": "collapsed",
            "query": "report",
        },
        field_filters={"artifact_role": "report"},
    )

    with _running_experiment_ui(db_path, "--limit", "200", "--page-size", "20", "--results-collapse", "collapsed") as base_url:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1400})
            page.goto(base_url + initial_query, wait_until="load", timeout=120000)
            _wait_for_sections(page)
            _wait_for_body_text(page, first_key)
            assert _results_expander_is_open(page) is False

            deep_link = page.get_by_label("Deep-Link / 直达链接").input_value()
            assert "view=artifact_catalog" in deep_link
            assert "f_artifact_role=report" in deep_link
            assert "results_collapse=collapsed" in deep_link
            selected_from_link = parse_qs(deep_link.lstrip("?")).get("selected", [""])[0]
            assert selected_from_link
            assert selected_from_link == first_key

            page.get_by_role("link", name="下一项链接 / Next Link").click()
            selected_after_switch, deep_link = _wait_for_selected_change_in_deep_link(page, first_key)
            _wait_for_body_text(page, selected_after_switch)
            assert "view=artifact_catalog" in deep_link
            assert "f_artifact_role=report" in deep_link
            assert "results_collapse=collapsed" in deep_link

            page2 = browser.new_page(viewport={"width": 1600, "height": 1400})
            page2.goto(base_url + deep_link, wait_until="load", timeout=120000)
            _wait_for_sections(page2)
            _wait_for_body_text(page2, selected_after_switch)
            _wait_for_selected_in_deep_link(page2, selected_after_switch)
            assert _results_expander_is_open(page2) is False
            assert page2.get_by_label("Deep-Link / 直达链接").input_value() == deep_link

            browser.close()
