from __future__ import annotations


def test_landing_card_from_trail_row_formats_discovery_metadata() -> None:
    from app import landing_card_from_trail_row

    row = {
        "id": 12,
        "name": "Aletsch - Bettmerhorn",
        "canton": "VS",
        "region": "Alps",
        "difficulty": "T2",
        "min_alt_m": 1950,
        "max_alt_m": 2872,
        "length_km": 6.0,
    }

    card = landing_card_from_trail_row(row, image_url="https://example.com/alps.jpg")

    assert card["title"] == "Aletsch - Bettmerhorn"
    assert card["distance"] == "6.0 km"
    assert card["duration"] == "1 day"
    assert card["status"] == "Safe Today"
    assert card["meta"] == "VS · Alps · T2 · 2872 m"
    assert card["image_url"] == "https://example.com/alps.jpg"
    assert card["image_notice"] == ""
    assert card["trail_id"] == "12"
    assert card["detail_url"] == "/Trail_Detail?trail_id=12"
    assert card["difficulty"] == "T2"
    assert card["ascent"] == "922 m"
    assert card["time_est"]
    assert card["length_value"] == "6.0 km"
    assert card["verdict"] == "SAFE"


def test_landing_card_marks_alpine_grades_as_avoid() -> None:
    from app import landing_card_from_trail_row

    row = {
        "id": 1,
        "name": "Matterhorn - Hornlihuette",
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
    assert card["verdict"] == "AVOID"
    assert card["verdict_class"] == "avoid"


def test_home_route_card_uses_find_card_markup(monkeypatch) -> None:
    import app

    rendered = []
    monkeypatch.setattr(app.st, "markdown", lambda html, **_: rendered.append(html))

    app._render_hero_card(
        {
            "detail_url": "/Trail_Detail?trail_id=12",
            "image_url": "https://example.com/alps.jpg",
            "image_notice": "",
            "status_class": "safe",
            "status": "Safe Today",
            "title": "Gornergrat Panorama",
            "duration": "1 day",
            "distance": "7.1 km",
            "meta": "VS · Alps · T2 · 3089 m",
            "difficulty": "T2",
            "ascent": "600 m",
            "time_est": "2 h 25 min",
            "length_value": "7.1 km",
            "verdict": "SAFE",
            "verdict_class": "safe",
            "verdict_emoji": "🟢",
        }
    )

    html = rendered[-1]
    assert html.startswith('<div class="hike-card-link">')
    assert 'class="hike-card-hitbox"' in html
    assert 'href="/Trail_Detail?trail_id=12"' in html
    assert '<div class="hike-card-image"' in html
    assert '<div class="hike-card-title">Gornergrat Panorama</div>' in html
    assert '<div class="hike-stats">' in html
    assert "hero-card" not in html
    assert "destination-card" not in html


def test_feature_card_is_the_navigation_target(monkeypatch) -> None:
    import app

    rendered = []
    monkeypatch.setattr(app.st, "markdown", lambda html, **_: rendered.append(html))

    app._render_feature_card(
        "&compass;",
        "Find a hike",
        "Answer a few trail preferences.",
        "/Find",
    )

    html = rendered[-1]
    assert "feature-card-link" in html
    assert 'href="/Find"' in html
    assert "Open Find a hike" not in html
