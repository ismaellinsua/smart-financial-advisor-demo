"""The generated pages of the website (ops/guias.py): what is published in docs/guias/, docs/herramientas/ and docs/tiktok/ is exactly what the
texts in ops/guias_texto.py and ops/herramientas_texto.py produce."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))

import guias  # noqa: E402
import guias_texto  # noqa: E402
import herramientas_texto  # noqa: E402


def test_the_published_guides_are_what_the_texts_produce():
    # If this fails: run «python ops/guias.py» and commit the result (never edit docs/guias/ by hand).
    assert guias.main(["--check"]) == 0


def test_the_texts_respect_the_limits_the_website_tests_apply():
    guias.validate()
    assert len(guias_texto.GUIDES) >= 11


def test_every_guide_answers_with_plain_text_and_names_a_sector_and_two_more_guides():
    for slug, guide in guias_texto.GUIDES.items():
        assert len(guide["related"]) >= 2 and slug not in guide["related"]
        assert guide["sectors"] and all(s in guias_texto.SECTOR for s in guide["sectors"])
        assert len(guide["faq"]) >= 3
        for question, answer in guide["faq"]:
            assert "<" not in answer and "<" not in question, f"{slug}: las preguntas frecuentes van sin etiquetas (son también los datos estructurados)"


def test_the_sitemap_lists_the_core_pages_both_hubs_every_guide_and_every_tool():
    xml = guias.sitemap()
    assert xml.count("<loc>") == len(guias.CORE) + 2 + len(guias_texto.GUIDES) + len(herramientas_texto.TOOLS)
    for page in ("guias/", "herramientas/", "tpv-tiendas/", "programa-gestion-pequenas-empresas/"):
        assert f"https://nirkana.es/{page}" in xml


def test_the_tiktok_landing_is_not_indexed_and_not_in_the_sitemap():
    page = guias.render_tiktok()
    assert '<meta name="robots" content="noindex, follow">' in page
    assert "tiktok" not in guias.sitemap()
    assert "tiktok" not in (ROOT / "docs" / "robots.txt").read_text().lower()   # a page that is not indexed must still be crawlable


def test_every_guide_has_valid_dates_and_a_new_one_says_it_was_published_not_updated():
    for slug, guide in guias_texto.GUIDES.items():
        published, updated = guias.dates(guide)
        assert published <= updated <= guias.DATE, slug
    page = guias.render_guide("comandas-y-pantalla-de-cocina-en-un-bar")
    assert "Publicada el" in page and "Actualizada el" not in page
