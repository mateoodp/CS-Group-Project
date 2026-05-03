"""Validate every seeded trail against Open-Meteo.

Run as::

    python -m scripts.validate_trails             # report failures only
    python -m scripts.validate_trails --prune     # rewrite trails_seed.json
                                                  # with the failures removed
    python -m scripts.validate_trails --workers 8 # tune parallelism

The script hits Open-Meteo's free forecast endpoint once per trail (in
parallel). A trail "passes" if the API returns at least one daily entry
for the next 7 days. Failures are usually transient — re-run before
pruning to avoid removing trails that just happened to time out.

We never need to call this in production; it exists so that maintainers
can keep the catalogue clean over time.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Ensure the project root is importable when run as `python scripts/validate_trails.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data import weather_fetcher  # noqa: E402

SEED_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "trails_seed.json"


def _probe(trail: dict) -> tuple[dict, bool, str]:
    """Try to fetch a 7-day forecast for a single trail."""
    try:
        data = weather_fetcher.fetch_forecast(trail["lat"], trail["lon"])
        n = len(data.get("daily", {}).get("time", []))
        return trail, n >= 1, f"{n} day(s)" if n else "empty daily block"
    except Exception as e:
        return trail, False, f"{e.__class__.__name__}: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prune", action="store_true",
        help="Rewrite trails_seed.json with failing trails removed.",
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    trails: list[dict] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    print(f"Probing {len(trails)} trail(s) with {args.workers} workers…\n")

    results: list[tuple[dict, bool, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_probe, t): t for t in trails}
        for i, fut in enumerate(as_completed(futures), start=1):
            res = fut.result()
            results.append(res)
            flag = "✓" if res[1] else "✗"
            if not res[1]:
                print(f"  {flag} {res[0]['name'][:40]:40} — {res[2]}")
            if i % 50 == 0:
                print(f"  …{i}/{len(trails)} probed")

    failures = [(t, msg) for t, ok, msg in results if not ok]
    print(f"\nResult: {len(trails) - len(failures)}/{len(trails)} OK, "
          f"{len(failures)} failure(s).")

    if failures:
        print("\nFailing trails:")
        for t, msg in failures:
            print(f"  - {t['name']} ({t['lat']:.3f}, {t['lon']:.3f}) — {msg}")

    if args.prune and failures:
        bad_keys = {(t["name"], t["lat"], t["lon"]) for t, _ in failures}
        kept = [t for t in trails
                if (t["name"], t["lat"], t["lon"]) not in bad_keys]
        SEED_PATH.write_text(
            json.dumps(kept, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\n✓ Wrote pruned catalogue: {len(kept)} trails.")
        print("  Bump SCHEMA_VERSION in data/db_manager.py so the DB re-seeds.")
    elif args.prune:
        print("\nNothing to prune — all trails passed.")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
