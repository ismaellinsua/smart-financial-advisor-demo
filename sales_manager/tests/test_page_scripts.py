"""The Content-Security-Policy allows only the app's own inline scripts, by hash: the policy and the scripts must agree."""

import re
from pathlib import Path

from core.page_scripts import SCRIPTS, script_src, script_tag, source_hash, streamlit_inline_scripts

ROOT = Path(__file__).resolve().parents[2]


def _policy() -> str:
    return re.search(r'Content-Security-Policy "([^"]+)"', (ROOT / "ops" / "deploy" / "Caddyfile").read_text()).group(1)


def test_the_container_policy_allows_exactly_the_apps_scripts():
    directive = next(d.strip() for d in _policy().split(";") if d.strip().startswith("script-src"))
    # A mismatch means a script or Streamlit changed: regenerate with `python -m core.page_scripts`.
    assert directive == script_src()
    assert "'unsafe-inline'" not in directive and "'unsafe-eval'" not in directive
    assert streamlit_inline_scripts(), "Streamlit's page changed: check which inline scripts it now needs"


def test_no_page_writes_a_script_of_its_own():
    """Every script goes through script_tag: one written inline elsewhere would be refused by the browser."""
    for path in [ROOT / "sales_manager" / "app.py", *(ROOT / "sales_manager").glob("ui/*.py"),
                 *(ROOT / "sales_manager").glob("core/*.py")]:
        if path.name == "page_scripts.py":
            continue
        text = path.read_text()
        assert "<script" not in text, f"{path.name}: use core.page_scripts.script_tag"
        assert not re.search(r"\son[a-z]+\s*=\s*['\"]", text), f"{path.name}: inline event handler"


def test_values_travel_outside_the_script_and_are_escaped():
    tag = script_tag("remember_business", name="nk_negocio", code='x"><script>alert(1)</script>')
    body = tag.split(">", 1)[1]
    assert body == SCRIPTS["remember_business"] + "</script>"  # the hashed text never changes
    assert 'data-code="x&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;"' in tag
    assert source_hash("") == "'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='"  # the well-known empty hash
