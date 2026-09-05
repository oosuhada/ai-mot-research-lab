#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


DEFAULT_PROFILE = Path.home() / "Library/Application Support/oosu-research-browser/chromium-profile"
DEFAULT_DOWNLOADS = Path("/Volumes/T9 SSD/server-data/ai-mot-research-lab/browser-downloads")
DEFAULT_MOUNT = Path("/Volumes/T9 SSD")
DEFAULT_SENTINEL = DEFAULT_MOUNT / ".oosu-server-storage"
EXPORT_FIELD_IDS = (
    "field_group_authors",
    "field_group_titles",
    "field_group_year",
    "field_group_eid",
    "field_group_sourceTitle",
    "field_group_citedBy",
    "field_group_sourceDocumentType",
    "field_group_doi",
    "field_group_openAccess",
    "field_group_affiliations",
    "field_group_serialIdentifiers",
    "field_group_publisher",
    "field_group_originalLanguage",
    # Scopus currently exposes the Abstract checkbox with this misspelled id.
    "field_group_abstact",
    "field_group_authorKeywords",
    "field_group_indexedKeywords",
)


class AuthenticationRequired(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export bounded recent Scopus results through the authenticated browser UI and import them."
    )
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path(os.environ.get("SCOPUS_BROWSER_PROFILE", DEFAULT_PROFILE)),
    )
    parser.add_argument(
        "--downloads",
        type=Path,
        default=Path(os.environ.get("SCOPUS_BROWSER_DOWNLOAD_ROOT", DEFAULT_DOWNLOADS)),
    )
    parser.add_argument("--axis", action="append", default=[], help="Restrict to one or more research-axis slugs")
    parser.add_argument(
        "--max-results-per-axis",
        type=int,
        default=int(os.environ.get("SCOPUS_BROWSER_MAX_RESULTS_PER_AXIS", "10")),
    )
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--no-import", action="store_true", help="Download only; do not call the Research CLI")
    return parser.parse_args()


def log(event: str, **fields: Any) -> None:
    payload = {"at": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def ensure_external_storage(downloads: Path) -> None:
    mount = Path(os.environ.get("PRIVATE_DATA_EXPECTED_MOUNT", DEFAULT_MOUNT)).expanduser()
    sentinel = Path(os.environ.get("PRIVATE_DATA_SENTINEL", DEFAULT_SENTINEL)).expanduser()
    minimum_gb = int(os.environ.get("PRIVATE_DATA_MIN_FREE_GB", "25"))
    if not mount.is_mount():
        raise RuntimeError(f"expected external mount is unavailable: {mount}")
    if not sentinel.is_file():
        raise RuntimeError(f"storage sentinel is missing: {sentinel}")
    downloads = downloads.expanduser()
    try:
        downloads.relative_to(mount)
    except ValueError as exc:
        raise RuntimeError("Scopus download root must live on the external storage mount") from exc
    downloads.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(mount).free / 1024**3
    if free_gb < minimum_gb:
        raise RuntimeError(f"T9 free space is below reserve: {free_gb:.1f} GiB < {minimum_gb} GiB")


def load_axes(repo: Path) -> list[Any]:
    api_src = repo / "apps" / "api" / "src"
    sys.path.insert(0, str(api_src))
    from research_lab.taxonomy import RESEARCH_AXES  # noqa: PLC0415

    return list(RESEARCH_AXES)


def visible_exact(page: Any, text: str) -> bool:
    locator = page.get_by_text(text, exact=True)
    for index in range(locator.count()):
        try:
            if locator.nth(index).is_visible():
                return True
        except Exception:
            continue
    return False


def ensure_authenticated(page: Any) -> Any:
    page.goto("https://www.scopus.com/pages/home#basic", wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(2_500)
    if visible_exact(page, "Sign in") or visible_exact(page, "Check access"):
        raise AuthenticationRequired("Scopus institutional browser session has expired")
    search = page.locator("input[id^=autosuggest-]").first
    try:
        search.wait_for(state="visible", timeout=15_000)
    except PlaywrightTimeoutError as exc:
        raise AuthenticationRequired("Scopus search input is unavailable; re-authentication may be required") from exc
    return search


def results_page_size(max_results: int) -> str:
    for allowed in (10, 20, 50, 100, 200):
        if max_results <= allowed:
            return str(allowed)
    return "200"


def select_recent_results(page: Any, query: str, max_results: int) -> int:
    search = ensure_authenticated(page)
    # Basic Scopus search defaults to Article title / Abstract / Keywords.
    field_select = page.locator("select").first
    if field_select.count() and field_select.is_visible():
        field_select.select_option("TITLE_ABS_KEY")
    search.fill(query)
    search.press("Enter")
    page.get_by_label("Select result 1", exact=True).wait_for(state="visible", timeout=30_000)
    page.wait_for_timeout(1_000)

    selects = page.locator("select")
    if selects.count() >= 3:
        sort_select = selects.nth(1)
        size_select = selects.nth(2)
        if sort_select.is_visible() and sort_select.input_value() != "plf-f":
            sort_select.select_option("plf-f")  # Date (newest)
            page.wait_for_timeout(1_500)
        size = results_page_size(max_results)
        if size_select.is_visible() and size_select.input_value() != size:
            size_select.select_option(size)
            page.wait_for_timeout(2_000)

    selected = 0
    for index in range(1, max_results + 1):
        checkbox = page.get_by_label(f"Select result {index}", exact=True)
        if not checkbox.count():
            break
        try:
            if checkbox.is_visible():
                checkbox.check()
                selected += 1
        except Exception:
            break
    return selected


def configure_export_fields(dialog: Any) -> None:
    for field_id in EXPORT_FIELD_IDS:
        checkbox = dialog.locator(f"#{field_id}")
        try:
            if checkbox.count() and checkbox.is_visible() and not checkbox.is_checked():
                checkbox.check()
        except Exception:
            # Scopus occasionally changes optional field ids. Required identity
            # fields are already selected by default, so an optional field miss
            # should not abort the whole run.
            continue


def export_selected_csv(page: Any, downloads: Path, axis_slug: str, selected: int) -> Path:
    page.get_by_text("Export", exact=True).click()
    page.wait_for_timeout(500)
    page.get_by_text("CSV", exact=True).click()
    dialog = page.get_by_role("dialog").last
    dialog.wait_for(state="visible", timeout=10_000)
    configure_export_fields(dialog)
    export_button = None
    buttons = dialog.get_by_role("button")
    for index in range(buttons.count()):
        button = buttons.nth(index)
        try:
            text = (button.inner_text() or "").strip()
            if button.is_visible() and button.is_enabled() and text.startswith("Export"):
                export_button = button
                break
        except Exception:
            continue
    if export_button is None:
        raise RuntimeError("Scopus CSV export button was not found")

    with page.expect_download(timeout=60_000) as download_info:
        export_button.click()
    download = download_info.value
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = downloads / f"scopus-{axis_slug}-{stamp}-{selected}.csv"
    download.save_as(str(destination))
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("Scopus export completed without a usable CSV file")
    return destination


def import_csv(repo: Path, csv_path: Path) -> dict[str, Any]:
    api_dir = repo / "apps" / "api"
    python = api_dir / ".venv-prod" / "bin" / "python"
    if not python.is_file():
        raise RuntimeError(f"production API interpreter is missing: {python}")
    completed = subprocess.run(
        [str(python), "-m", "research_lab.cli", "import-scopus-csv", "--input", str(csv_path)],
        cwd=api_dir,
        text=True,
        capture_output=True,
        timeout=900,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Scopus import failed: {completed.stderr.strip() or completed.stdout.strip()}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Scopus import returned non-JSON output") from exc


def write_status(repo: Path, payload: dict[str, Any]) -> None:
    root = repo / "artifacts" / "scopus-browser-sync"
    root.mkdir(parents=True, exist_ok=True)
    (root / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    repo = args.repo.expanduser().resolve()
    profile = args.profile.expanduser()
    downloads = args.downloads.expanduser()
    max_results = min(max(args.max_results_per_axis, 1), 200)
    try:
        ensure_external_storage(downloads)
        axes = load_axes(repo)
        if args.axis:
            requested = set(args.axis)
            axes = [axis for axis in axes if axis.slug in requested]
            missing = requested - {axis.slug for axis in axes}
            if missing:
                raise RuntimeError(f"unknown research axis: {', '.join(sorted(missing))}")

        results: list[dict[str, Any]] = []
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=args.headless,
                accept_downloads=True,
                downloads_path=str(downloads),
                no_viewport=True,
                args=["--start-maximized"],
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                ensure_authenticated(page)
                for axis in axes:
                    selected = select_recent_results(page, axis.openalex_query, max_results)
                    if selected == 0:
                        log("axis_empty", axis=axis.slug)
                        results.append({"axis": axis.slug, "selected": 0, "status": "empty"})
                        continue
                    csv_path = export_selected_csv(page, downloads, axis.slug, selected)
                    item: dict[str, Any] = {
                        "axis": axis.slug,
                        "selected": selected,
                        "csv": str(csv_path),
                        "bytes": csv_path.stat().st_size,
                    }
                    log("axis_exported", **item)
                    if not args.no_import:
                        imported = import_csv(repo, csv_path)
                        item["import"] = {
                            "inserted_count": imported.get("inserted_count", 0),
                            "updated_count": imported.get("updated_count", 0),
                            "error_count": imported.get("error_count", 0),
                            "run_id": imported.get("run_id"),
                        }
                        log("axis_imported", axis=axis.slug, **item["import"])
                    results.append(item)
            finally:
                context.close()

        status = {
            "status": "completed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "max_results_per_axis": max_results,
            "axes": results,
        }
        write_status(repo, status)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    except AuthenticationRequired as exc:
        status = {
            "status": "authentication_required",
            "at": datetime.now(timezone.utc).isoformat(),
            "detail": str(exc),
        }
        write_status(repo, status)
        log("authentication_required", detail=str(exc))
        return 75
    except Exception as exc:
        status = {
            "status": "failed",
            "at": datetime.now(timezone.utc).isoformat(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        write_status(repo, status)
        log("failed", error=status["error"])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
