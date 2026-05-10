from __future__ import annotations


def test_landing_card_from_trail_row_formats_discovery_metadata() -> None:
    from app import landing_card_from_trail_row

    row = {
        "id": 12,
        "name": "Aletsch — Bettmerhorn",
        "canton": "VS",
        "region": "Alps",
        "difficulty": "T2",
        "min_alt_m": 1950,
        "max_alt_m": 2872,
        "length_km": 6.0,
    }

    card = landing_card_from_trail_row(row, image_url="https://example.com/alps.jpg")

    assert card["title"] == "Aletsch — Bettmerhorn"
    assert card["distance"] == "6.0 km"
    assert card["duration"] == "1 day"
    assert card["status"] == "Safe Today"
    assert card["meta"] == "VS · Alps · T2 · 2872 m"
    assert card["image_url"] == "https://example.com/alps.jpg"


def test_landing_card_marks_alpine_grades_as_avoid() -> None:
    from app import landing_card_from_trail_row

    row = {
        "id": 1,
        "name": "Matterhorn — Hörnlihütte",
        "canton": "VS",
        "region": "Alps",
        "difficulty": "T4",
        "min_alt_m": 2583,
        "max_alt_m": 3260,
        "length_km": 8.5,
    }

    card = landing_card_from_trail_row(
        row, image_url="https://example.com/matterhorn.jpg"
    )

    assert card["duration"] == "Full day"
    assert card["status"] == "Avoid"
