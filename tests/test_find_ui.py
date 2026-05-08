from __future__ import annotations

import importlib.util
from pathlib import Path


def test_find_results_use_full_card_links_without_view_details_button() -> None:
    source = Path("pages/1_Find.py").read_text(encoding="utf-8")

    assert 'class="hike-card-link"' in source
    assert "hike-card-hitbox" in source
    assert 'class="image-notice"' in source
    assert 'image_info["notice"]' in source
    assert "View details" not in source


def test_find_result_card_outputs_plain_card_markup(monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location("find_page", "pages/1_Find.py")
    assert spec and spec.loader
    find_page = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(find_page)

    rendered = []
    monkeypatch.setattr(
        find_page.st, "markdown", lambda html, **_: rendered.append(html)
    )
    monkeypatch.setattr(
        find_page,
        "route_image_info",
        lambda _: {
            "url": "https://example.com/uetliberg.jpg",
            "notice": "",
            "is_fallback": False,
        },
    )

    result = {
        "trail": {
            "id": 9,
            "name": "Uetliberg — Felsenegg",
            "difficulty": "T1",
            "canton": "ZH",
            "region": "Mittelland",
            "min_alt_m": 450,
            "max_alt_m": 849,
            "length_km": 6.0,
        },
        "adjusted": "SAFE",
        "snapshot": {"temp_c": 13, "wind_kmh": 5},
        "caveats": [],
    }

    find_page._render_result_card(result, target_date=None)

    html = rendered[-1]
    assert html.startswith('<div class="hike-card-link"')
    assert 'class="hike-card-hitbox"' in html
    assert 'href="/Trail_Detail?trail_id=9"' in html
    assert "<span class='verdict-pill safe'>" in html
    assert "\n        <a class=\"hike-card-link\"" not in html
    assert "class=\"hike-card-title\"" in html
