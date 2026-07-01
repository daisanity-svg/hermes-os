"""UI structure and responsiveness checks for Chairman Desktop."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

HTML_PATH = Path(__file__).resolve().parents[1] / "docs" / "command-center" / "index.html"

REQUIRED_MODULE_IDS = {
    "panel-company",
    "panel-brief",
    "panel-department",
    "panel-decision",
    "ws-projects",
    "ws-workflows",
    "ws-runs",
    "ws-scheduler",
    "ws-inbox",
    "ws-packages",
}

FRIENDLY_TERMS = {
    "進行中專案",
    "進行中流程",
    "系統執行記錄",
    "任務待辦",
    "套件時程",
    "Founder Inbox",
}

FORBIDDEN_LEGACY_TERMS = {
    "Auto Scheduler",
    "Hermes Runs Mirror",
    "Active Projects",
    "Active Workflows",
    "Package Timeline",
}


def _read_html() -> str:
    if not HTML_PATH.exists():
        pytest.fail(f"Chairman Desktop HTML not found at {HTML_PATH}")
    return HTML_PATH.read_text(encoding="utf-8")


def test_html_is_viewable_and_utf8():
    html = _read_html()
    assert '<meta charset="UTF-8" />' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1.0" />' in html
    assert "Chairman Desktop" in html


def test_required_modules_present():
    html = _read_html()
    missing = [mod_id for mod_id in REQUIRED_MODULE_IDS if f'id="{mod_id}"' not in html]
    assert not missing, f"Missing required module IDs: {missing}"


def test_no_engineering_jargon_in_headings():
    html = _read_html()
    # Extract all text nodes inside <h2> and <h3> tags as a coarse approximation.
    headings = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html, flags=re.DOTALL)
    plain_headings = [re.sub(r"<[^>]+>", "", h).strip() for h in headings]
    bad = [h for h in plain_headings if h in FORBIDDEN_LEGACY_TERMS]
    assert not bad, f"Engineering jargon still present in headings: {bad}"


def test_friendly_terms_present():
    html = _read_html()
    missing = [term for term in FRIENDLY_TERMS if term not in html]
    assert not missing, f"Expected friendly terms missing: {missing}"


def test_responsive_breakpoints_exist():
    html = _read_html()
    # sanity: must define at least one mobile breakpoint and one workspace breakpoint
    assert "@media (max-width: 640px)" in html, "Missing 640px breakpoint"
    assert "@media (max-width: 420px)" in html, "Missing 420px breakpoint"


def test_tap_target_min_height():
    html = _read_html()
    # Workspace toggle and select should have min-height to meet mobile tap guidelines.
    assert "min-height: 36px" in html, "Missing min-height on interactive elements"
    assert "touch-action: manipulation" in html, "Missing touch-action optimization"


def test_friendly_api_fallback_messages():
    html = _read_html()
    # Ensure generic engineering-style error text is replaced by friendly phrasing.
    assert "讀取失敗，" not in html or "請稍後再試" in html
    # The workspace fallback in particular should not use terse jargon.
    assert "載入失敗，請稍後再試。" in html
