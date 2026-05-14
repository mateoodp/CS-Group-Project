from __future__ import annotations


def test_route_image_search_terms_include_route_endpoints() -> None:
    from utils.route_images import route_image_search_terms

    trail = {
        "name": "Mannlichen — Kleine Scheidegg",
        "canton": "BE",
        "region": "Alps",
    }

    terms = route_image_search_terms(trail)

    assert terms[0] == "Mannlichen — Kleine Scheidegg BE hiking"
    assert "Mannlichen mountain Switzerland" in terms
    assert "Kleine Scheidegg mountain Switzerland" in terms


def test_trail_detail_url_uses_query_param() -> None:
    from utils.route_images import trail_detail_url

    assert trail_detail_url({"id": 42}) == "/Trail_Detail?trail_id=42"


def test_trail_id_from_query_params_accepts_streamlit_shape() -> None:
    from utils.route_images import trail_id_from_query_params

    assert trail_id_from_query_params({"trail_id": "42"}) == 42
    assert trail_id_from_query_params({"trail_id": ["42"]}) == 42
    assert trail_id_from_query_params({"trail_id": "not-a-number"}) is None


def test_known_route_image_uses_specific_real_commons_photo() -> None:
    from utils.route_images import route_image_url

    image_url = route_image_url(
        {"name": "Gornergrat Panorama", "canton": "VS", "region": "Alps"}
    )

    assert image_url.startswith("https://commons.wikimedia.org/w/thumb.php?")
    assert "Aerial_panorama_of_the_Gornergrat_170622.jpg" in image_url


def test_unknown_route_image_uses_labelled_unsplash_fallback() -> None:
    from utils.route_images import route_image_info

    image_info = route_image_info(
        {"name": "Example Trail", "canton": "CH", "region": "Alps"}
    )

    assert image_info["url"].startswith("https://images.unsplash.com/")
    assert image_info["is_fallback"] is True
    assert image_info["notice"] == "Illustrative Unsplash image - not the actual route"


def test_route_image_ignores_unrelated_search_results(monkeypatch) -> None:
    import utils.route_images as route_images

    monkeypatch.setattr(
        route_images,
        "fetch_trail_images",
        lambda _term, limit=5: [
            {"title": "CH.VS.Zermatt 2021-10-17 Matterhorn 8726.jpg"},
            {"title": "CH.ZH.Hausen-am-Albis 2022-07-02 Albishorn.jpg"},
        ],
    )

    image_url = route_images._route_image_url_cached.__wrapped__(
        "Albis — Albishorn", "ZH", "Mittelland"
    )

    assert "Albishorn" in image_url
    assert "Matterhorn" not in image_url
