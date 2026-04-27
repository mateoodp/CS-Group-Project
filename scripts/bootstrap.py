"""End-to-end bootstrap: DB → archive fetch → train model.

Run from the project root:

    python -m scripts.bootstrap                       # default: 30 trails, 1 yr
    python -m scripts.bootstrap --limit 60            # widen the training set
    python -m scripts.bootstrap --limit 0             # all trails (slow)
    python -m scripts.bootstrap --years 2 --limit 30  # full archive depth

The script always seeds *all* trails into the DB (the map needs them).
``--limit`` only controls how many of them get historical weather + go into
the ML training pool — the model generalises across trails since features
are mostly weather, so a few dozen are plenty.
"""

from __future__ import annotations

import argparse
import sys
import time

from data import db_manager, weather_fetcher
from ml import trail_classifier


def run(years: int = 1, limit: int = 30) -> None:
    print("→ Setting up database…")
    db_manager.setup_db()

    trails = db_manager.get_all_trails()
    print(f"→ {len(trails)} trails seeded.")

    target = trails if limit <= 0 else trails[:limit]
    print(
        f"→ Fetching {years} year(s) of historical weather for "
        f"{len(target)} trail(s)…"
    )
    errors: list[tuple[str, str]] = []
    for i, t in enumerate(target, 1):
        t0 = time.perf_counter()
        try:
            n = weather_fetcher.seed_historical_weather(
                t["id"], t["lat"], t["lon"], years=years
            )
            dt = time.perf_counter() - t0
            print(f"  [{i:3d}/{len(target)}] {t['name']:40s} · {n} rows in {dt:.1f}s")
        except Exception as e:
            errors.append((t["name"], str(e)))
            print(f"  [{i:3d}/{len(target)}] {t['name']:40s} · FAILED ({e})")

    if errors:
        print(f"\n⚠️  {len(errors)} trail(s) failed to fetch.")

    print("\n→ Training Random Forest…")
    metrics = trail_classifier.retrain_from_db()
    print(f"  Accuracy : {metrics['accuracy']:.1%}")
    print(f"  Rows     : {metrics['n_samples']:,} "
          f"({metrics['n_train']} train / {metrics['n_test']} test)")
    print(f"  Labels   : {metrics['label_distribution']}")
    print(f"  Top feat : {metrics['feature_importances'][0]}")
    print("\n✅ Bootstrap complete. Run `streamlit run app.py`.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="One-shot setup for the hiking forecaster.")
    p.add_argument("--years", type=int, default=1,
                   help="Years of archive weather to fetch (1–2). Default: 1.")
    p.add_argument("--limit", type=int, default=30,
                   help="Max trails to fetch archive weather for. "
                        "0 = all trails. Default: 30 (~10s).")
    args = p.parse_args(argv)
    run(years=args.years, limit=args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
