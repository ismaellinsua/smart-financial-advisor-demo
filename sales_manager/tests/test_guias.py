"""The website guides (ops/guias.py): what is published in docs/guias/ is exactly what the texts in ops/guias_texto.py produce."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))

import guias  # noqa: E402
import guias_texto  # noqa: E402


def test_the_published_guides_are_what_the_texts_produce():
    # If this fails: run «python ops/guias.py» and commit the result (never edit docs/guias/ by hand).
    assert guias.main(["--check"]) == 0


def test_the_texts_respect_the_limits_the_website_tests_apply():
    guias.validate()
    assert len(guias_texto.GUIDES) >= 7


def test_every_guide_answers_with_plain_text_and_names_a_sector_and_two_more_guides():
    for slug, guide in guias_texto.GUIDES.items():
        assert len(guide["related"]) >= 2 and slug not in guide["related"]
        assert guide["sectors"] and all(s in guias_texto.SECTOR for s in guide["sectors"])
        assert len(guide["faq"]) >= 3
        for question, answer in guide["faq"]:
            assert "<" not in answer and "<" not in question, f"{slug}: las preguntas frecuentes van sin etiquetas (son también los datos estructurados)"


def test_the_sitemap_lists_the_core_pages_the_hub_and_every_guide():
    xml = guias.sitemap()
    assert xml.count("<loc>") == len(guias.CORE) + 1 + len(guias_texto.GUIDES)
    assert "https://nirkana.es/guias/" in xml and "https://nirkana.es/tpv-tiendas/" in xml
