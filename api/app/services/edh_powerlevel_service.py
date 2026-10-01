"""Scrape deck statistics from https://edhpowerlevel.com.

The site is a client-side app: all scoring happens in the browser after the
page loads, so a plain HTTP fetch returns no numbers. We drive a headless
Chromium via Playwright instead:

1. Encode the decklist into the site's own ``?d=`` URL format (the same URL
   the site pushes to the address bar after "Analyze List").
2. Poll the rendered page until the stat values stop changing (the page
   renders once from cached card data, then again after its card API
   responds, so the first numbers shown are not final).
3. Read the values and cache the result on disk, keyed by the normalized
   decklist.

The decklist is expected in Moxfield export format, commander(s) in a
trailing ``COMMANDER`` section::

    1 Sol Ring
    1 Arcane Signet
    ...

    COMMANDER
    1 Atraxa, Praetors' Voice

Standalone debugging (run from the ``api`` directory)::

    python -m app.services.edh_powerlevel_service deck.txt
    python -m app.services.edh_powerlevel_service deck.txt --no-cache --headful
    type deck.txt | python -m app.services.edh_powerlevel_service -
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

BASE_URL = "https://edhpowerlevel.com/"

# Resolves to <repo>/data locally and /data inside the api container (both
# gitignored / volume-mounted).
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "edhpowerlevel_cache"
CACHE_DIR = Path(os.environ.get("EDHPL_CACHE_DIR", _DEFAULT_CACHE_DIR))
CACHE_TTL_SECONDS = int(os.environ.get("EDHPL_CACHE_TTL_SECONDS", 7 * 24 * 3600))

# Bump when the shape of the returned dict changes so stale cache entries
# are ignored.
_CACHE_VERSION = 1

_LOAD_TIMEOUT_S = 45.0
_POLL_INTERVAL_S = 0.5
# Consecutive identical snapshots required before we trust the numbers.
_STABLE_POLLS = 4
# Parallel page loads allowed against the site at once.
_MAX_CONCURRENT_PAGES = int(os.environ.get("EDHPL_MAX_CONCURRENT_PAGES", 2))


class EdhPowerLevelError(RuntimeError):
    pass


# --- Decklist → URL --------------------------------------------------------


def normalize_decklist(decklist: str) -> str:
    lines = [line.strip() for line in decklist.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def build_url(decklist: str) -> str:
    # Mirrors the site's own encoding: one line per "~", words joined with
    # "+", terminated by "~Z~".
    lines = normalize_decklist(decklist).split("\n")
    return BASE_URL + "?d=" + "~".join(quote_plus(line) for line in lines) + "~Z~"


# --- Page extraction -------------------------------------------------------

# Runs in the page. Returns raw strings; parsing happens in Python so it is
# easy to debug from the CLI with --raw.
_EXTRACT_JS = r"""
() => {
  const main = document.querySelector('main');
  if (!main) return null;
  const text = main.innerText || '';
  const textOf = (el) => (el ? el.textContent.trim() : null);

  const stats = {};
  for (const el of document.querySelectorAll('.result')) {
    const cls = [...el.classList].find(c => c.startsWith('res-'));
    if (cls) stats[cls.slice(4)] = textOf(el.querySelector('.text-total'));
  }

  const accordion = {};
  for (const item of document.querySelectorAll('.accordion-item')) {
    const title = textOf(item.querySelector('.accordion-button'));
    const body = item.querySelector('.accordion-collapse, .accordion-body');
    if (title && body) accordion[title] = body.textContent.replace(/\s+/g, ' ').trim();
  }

  // Requirement Tracker: <strong>Label: N</strong><ul><li>card</li>...</ul>
  const tracker = [];
  for (const label of document.querySelectorAll('.bracket-tracker strong')) {
    const list = label.nextElementSibling;
    tracker.push({
      label: textOf(label),
      items: list && list.tagName === 'UL' ? [...list.querySelectorAll('li')].map(textOf) : [],
    });
  }

  const cards = [];
  const table = document.querySelector('table.table-dark');
  if (table) {
    for (const row of table.querySelectorAll('tbody tr')) {
      const cells = row.querySelectorAll('td');
      if (cells.length < 5) continue;
      const nameButton = cells[1].querySelector('.detail-button');
      cards.push({
        qty: textOf(cells[0]),
        name: nameButton ? nameButton.firstChild.textContent.trim() : textOf(cells[1]),
        colors: [...cells[2].querySelectorAll('.visually-hidden')].map(e => e.textContent.trim()),
        playability: textOf(cells[3]),
        impact: textOf(cells[4]),
      });
    }
  }

  const warning = [...main.querySelectorAll('*')].find(
    e => e.childElementCount > 0 && /^⚠️ Deck Scan Warning/.test(e.textContent.trim())
  );

  return {
    decklist_field: (document.querySelector('#decklist') || {}).value || '',
    imported: (text.match(/(\d+) total cards imported/) || [])[1] || null,
    stats,
    bracket: (text.match(/Commander Bracket:\s*(\d+)/) || [])[1] || null,
    accordion,
    tracker,
    screw: textOf(document.querySelector('.flood-graph .screw')),
    sweet: textOf(document.querySelector('.flood-graph .sweet')),
    flood: textOf(document.querySelector('.flood-graph .flood')),
    market_value: (text.match(/Total Market Value:\s*\$([\d,.]+)/) || [])[1] || null,
    warning: warning ? warning.textContent.replace(/\s+/g, ' ').trim() : null,
    cards,
  };
}
"""


def _snapshot_is_ready(raw: dict[str, Any] | None) -> bool:
    # An unparseable ?d= makes the site fall back to its built-in sample deck
    # with an empty textarea, so an empty field means "not our deck".
    return bool(
        raw
        and raw.get("decklist_field")
        and raw.get("imported")
        and raw.get("stats", {}).get("power-level")
    )


def _snapshot_key(raw: dict[str, Any]) -> str:
    return json.dumps(
        [raw["imported"], raw["stats"], raw["bracket"], raw["screw"], raw["flood"], len(raw["cards"])],
        sort_keys=True,
    )


# --- Parsing ---------------------------------------------------------------


def _num(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group()) if match else None


def _int(value: str | None) -> int | None:
    number = _num(value)
    return int(number) if number is not None else None


_TRACKER_KEYS = {
    "Extra Turns": "extra_turns",
    "Mass Land Denial": "mass_land_denial",
    "Early 2-Card Combos": "early_two_card_combos",
    "Late 2-Card Combos": "late_two_card_combos",
    "Game Changers": "game_changers",
}


def _parse_bracket_details(accordion: dict[str, str], tracker: list[dict[str, Any]]) -> dict[str, Any]:
    details = accordion.get("Your Bracket Details", "")

    def match_int(pattern: str) -> int | None:
        match = re.search(pattern, details)
        return int(match.group(1)) if match else None

    requirements: dict[str, Any] = {}
    for entry in tracker:
        label, _, count = (entry["label"] or "").partition(":")
        key = _TRACKER_KEYS.get(label.strip()) or re.sub(r"\W+", "_", label.strip().lower())
        requirements[key] = {"count": _int(count), "cards": entry["items"]}

    return {
        "recommended": match_int(r"Recommended Bracket:\s*(\d+)"),
        "minimum": match_int(r"Minimum Bracket:\s*(\d+)"),
        "requirements": requirements,
        "details_text": details or None,
    }


def _parse(raw: dict[str, Any], url: str) -> dict[str, Any]:
    stats = raw["stats"]
    cards = [
        {
            "name": card["name"],
            # The qty column shows 👑 for commanders and 🏆 for game changers
            # instead of a number; both are always singletons.
            "quantity": int(card["qty"]) if (card["qty"] or "").isdigit() else 1,
            "is_commander": card["qty"] == "👑",
            "is_game_changer": card["qty"] == "🏆",
            "colors": card["colors"],
            "playability_pct": _num(card["playability"]),
            "impact": _num(card["impact"]),
        }
        for card in raw["cards"]
    ]
    return {
        "source": "edhpowerlevel.com",
        "url": url,
        "cards_imported": _int(raw["imported"]),
        "power_level": _num(stats.get("power-level")),
        "tipping_point": _num(stats.get("tipping-point")),
        "efficiency": _num(stats.get("efficiency")),
        "impact": _num(stats.get("impact")),
        "score": _num(stats.get("score")),
        "average_playability_pct": _num(stats.get("playability")),
        "bracket": _int(raw["bracket"]),
        "bracket_details": _parse_bracket_details(raw["accordion"], raw["tracker"]),
        "mana": {
            "screw_pct": _num(raw["screw"]),
            "sweet_spot_pct": _num(raw["sweet"]),
            "flood_pct": _num(raw["flood"]),
        },
        "market_value_usd": _num(raw["market_value"]),
        "scan_warning": raw["warning"],
        "cards": cards,
    }


# --- Browser ---------------------------------------------------------------

_playwright = None
_browser = None
# asyncio primitives are bound to one event loop; recreate them if the loop
# changes (e.g. repeated fetch_power_level_sync calls).
_sync_loop: asyncio.AbstractEventLoop | None = None
_browser_lock: asyncio.Lock
_page_semaphore: asyncio.Semaphore


def _ensure_sync_primitives() -> None:
    global _sync_loop, _browser_lock, _page_semaphore
    loop = asyncio.get_running_loop()
    if _sync_loop is not loop:
        _sync_loop = loop
        _browser_lock = asyncio.Lock()
        _page_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_PAGES)


async def _get_browser(headless: bool = True):
    global _playwright, _browser
    _ensure_sync_primitives()
    async with _browser_lock:
        if _browser is None or not _browser.is_connected():
            from playwright.async_api import async_playwright

            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(headless=headless)
        return _browser


async def close_browser() -> None:
    global _playwright, _browser
    _ensure_sync_primitives()
    async with _browser_lock:
        if _browser is not None:
            await _browser.close()
            _browser = None
        if _playwright is not None:
            await _playwright.stop()
            _playwright = None


async def _scrape_raw(url: str, *, headless: bool, timeout_s: float) -> dict[str, Any]:
    browser = await _get_browser(headless=headless)
    async with _page_semaphore:
        # Fresh context per deck: the site caches card data in localStorage,
        # and we want each run independent of the previous one.
        context = await browser.new_context()
        try:
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)

            deadline = time.monotonic() + timeout_s
            last_key: str | None = None
            stable = 0
            raw: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                raw = await page.evaluate(_EXTRACT_JS)
                if _snapshot_is_ready(raw):
                    key = _snapshot_key(raw)
                    stable = stable + 1 if key == last_key else 1
                    last_key = key
                    if stable >= _STABLE_POLLS:
                        return raw
                await asyncio.sleep(_POLL_INTERVAL_S)

            if raw and raw.get("stats", {}).get("power-level") and not raw.get("decklist_field"):
                raise EdhPowerLevelError(
                    "edhpowerlevel.com did not accept the decklist (it fell back to its sample deck)."
                )
            raise EdhPowerLevelError(f"Timed out after {timeout_s:.0f}s waiting for results.")
        finally:
            await context.close()


# --- Cache -----------------------------------------------------------------


def _cache_path(decklist: str) -> Path:
    digest = hashlib.sha256(f"v{_CACHE_VERSION}\n{decklist}".encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def _read_cache(decklist: str) -> dict[str, Any] | None:
    path = _cache_path(decklist)
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if time.time() - entry.get("fetched_at", 0) > CACHE_TTL_SECONDS:
        return None
    return entry


def _write_cache(decklist: str, result: dict[str, Any]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(decklist).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# --- Public API ------------------------------------------------------------


async def fetch_power_level(
    decklist: str,
    *,
    use_cache: bool = True,
    headless: bool = True,
    timeout_s: float = _LOAD_TIMEOUT_S,
    include_raw: bool = False,
) -> dict[str, Any]:
    normalized = normalize_decklist(decklist)
    if not normalized:
        raise ValueError("Decklist is empty.")

    if use_cache and not include_raw:
        cached = _read_cache(normalized)
        if cached is not None:
            return {**cached, "cached": True}

    url = build_url(normalized)
    raw = await _scrape_raw(url, headless=headless, timeout_s=timeout_s)
    result = {**_parse(raw, url), "fetched_at": time.time()}
    _write_cache(normalized, result)
    if include_raw:
        result["raw"] = raw
    return {**result, "cached": False}


def fetch_power_level_sync(decklist: str, **kwargs: Any) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        try:
            return await fetch_power_level(decklist, **kwargs)
        finally:
            await close_browser()

    return asyncio.run(run())


# --- CLI -------------------------------------------------------------------


def _main() -> None:
    parser = argparse.ArgumentParser(description="Score a decklist on edhpowerlevel.com.")
    parser.add_argument("decklist", help="Path to a Moxfield-format decklist, or '-' for stdin.")
    parser.add_argument("--no-cache", action="store_true", help="Ignore and overwrite the cache.")
    parser.add_argument("--headful", action="store_true", help="Show the browser window.")
    parser.add_argument("--raw", action="store_true", help="Include the raw scraped strings.")
    parser.add_argument("--cards", action="store_true", help="Include the per-card table.")
    parser.add_argument("--url-only", action="store_true", help="Print the edhpowerlevel URL and exit.")
    parser.add_argument("--timeout", type=float, default=_LOAD_TIMEOUT_S)
    args = parser.parse_args()

    if args.decklist == "-":
        decklist = sys.stdin.read()
    else:
        decklist = Path(args.decklist).read_text(encoding="utf-8")

    if args.url_only:
        print(build_url(decklist))
        return

    started = time.monotonic()
    result = fetch_power_level_sync(
        decklist,
        use_cache=not args.no_cache,
        headless=not args.headful,
        timeout_s=args.timeout,
        include_raw=args.raw,
    )
    if not args.cards:
        result.pop("cards", None)
    result["elapsed_s"] = round(time.monotonic() - started, 2)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
