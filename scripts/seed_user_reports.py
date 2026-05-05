"""Insert representative user reports for demo purposes.

Run once: python -m scripts.seed_user_reports
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from data import db_manager

SEED_REPORTS = [
    # (trail_name_substring, n_reports, label_weights)
    ("Matterhorn",  5, {"SAFE": 0.1, "BORDERLINE": 0.5, "AVOID": 0.4}),
    ("Eiger Trail", 8, {"SAFE": 0.6, "BORDERLINE": 0.3, "AVOID": 0.1}),
    ("Rigi",        6, {"SAFE": 0.7, "BORDERLINE": 0.2, "AVOID": 0.1}),
    ("Weissfluh",   5, {"SAFE": 0.2, "BORDERLINE": 0.4, "AVOID": 0.4}),
    ("Pilatus",     7, {"SAFE": 0.5, "BORDERLINE": 0.3, "AVOID": 0.2}),
]

COMMENTS = [
    "Trail was in good condition.",
    "Icy patches above 2000m, crampons recommended.",
    "Beautiful day, no issues.",
    "Turned back due to unexpected snowfall.",
    "Wet and slippery after rain.",
    "Well marked, enjoyable hike.",
    "",
]


def run() -> None:
    db_manager.setup_db()
    trails = db_manager.get_all_trails()
    today = date.today()
    inserted = 0

    for substring, n, weights in SEED_REPORTS:
        match = next(
            (t for t in trails if substring.lower() in t["name"].lower()),
            None,
        )
        if match is None:
            print(f"  No trail found for '{substring}', skipping.")
            continue
        labels = list(weights.keys())
        probs = list(weights.values())
        for _ in range(n):
            label = random.choices(labels, weights=probs)[0]
            report_date = today - timedelta(days=random.randint(0, 14))
            comment = random.choice(COMMENTS)
            try:
                db_manager.insert_user_report(
                    trail_id=match["id"],
                    report_date=report_date,
                    user_label=label,
                    comment=comment,
                )
                inserted += 1
            except Exception as e:
                print(f"  Skipped duplicate: {e}")

    print(f"Inserted {inserted} user reports.")


if __name__ == "__main__":
    run()
