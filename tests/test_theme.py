from __future__ import annotations


def test_status_class_normalizes_verdict_labels() -> None:
    from utils.theme import status_class

    assert status_class("SAFE") == "safe"
    assert status_class("Safe Today") == "safe"
    assert status_class("BORDERLINE") == "borderline"
    assert status_class("—") == "unknown"


def test_stat_pills_html_escapes_labels_and_values() -> None:
    from utils.theme import stat_pills_html

    html = stat_pills_html([("A <trail>", "5 & ready")])

    assert "A &lt;trail&gt;" in html
    assert "5 &amp; ready" in html
    assert "stat-pill" in html


def test_theme_exposes_alpine_background_and_card_images() -> None:
    from utils.theme import ALPINE_BACKGROUND_IMAGE, image_for_index

    assert ALPINE_BACKGROUND_IMAGE.startswith("https://")
    assert image_for_index(0).startswith("https://")
    assert image_for_index(99) == image_for_index(99)


def test_theme_styles_streamlit_widget_labels() -> None:
    from utils.theme import APP_THEME_CSS

    assert '[data-testid="stWidgetLabel"]' in APP_THEME_CSS
    assert "font-family" in APP_THEME_CSS
    assert "border-radius: 16px" in APP_THEME_CSS
