"""Every script NirKanA adds to its pages, as fixed text.

The server's Content-Security-Policy (ops/deploy/Caddyfile) does not allow inline scripts in general
('unsafe-inline'): only these, by the SHA-256 of their exact text. So an attacker who managed to slip a <script> into a
page would not get it run. A script's values (a cookie's name, a business code) never go into its text, which must
not change: they travel in data- attributes and the script reads them from document.currentScript.dataset.

`python -m core.page_scripts` prints the script-src the Caddyfile must carry; a test checks the two agree, also with
the inline script of the installed Streamlit's own page.
"""

import base64
import hashlib
from html import escape

SCRIPTS = {
    # The sign-in cookie. Inside the container the server writes it (ops/deploy/sessions.py): HttpOnly, so no script
    # on the page can read it. Elsewhere (Streamlit Cloud, local runs) that service does not exist and the page writes
    # it itself. Over HTTPS the name carries the __Host- prefix: the browser then refuses it unless it is Secure, for
    # this exact host and path /, so no other subdomain or plain-HTTP page can plant or overwrite it.
    "session_cookie": """
(() => {
  const data = document.currentScript.dataset, secure = location.protocol === "https:";
  const byPage = () => {
    document.cookie = (secure ? "__Host-" : "") + data.name + "=" + data.value + "; Path=/; Max-Age=" + data.age
      + "; SameSite=Strict" + (secure ? "; Secure" : "");
    if (secure) document.cookie = data.name + "=; Path=/; Max-Age=0; SameSite=Strict";  // the old, unprefixed one
  };
  if (!secure) return byPage();
  fetch("/_nk/sesion", {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({name: data.name, token: data.value})})
    .then((r) => { if (r.status !== 204) byPage(); }).catch(byPage);
})();
""",
    # The last business used on this device (only its code, which is in the address anyway), for a year.
    "remember_business": """
document.cookie = document.currentScript.dataset.name + "=" + document.currentScript.dataset.code
  + "; Path=/; Max-Age=31536000; SameSite=Lax" + (location.protocol === "https:" ? "; Secure" : "");
""",
    # The web app manifest and icons, so phones and computers offer to install NirKanA as an app. Streamlit has no way
    # to add them to the page head, so a script does.
    "installable": """
(() => {
  if (document.querySelector('link[rel="manifest"]')) return;
  const add = (tag, attrs) => document.head.appendChild(Object.assign(document.createElement(tag), attrs));
  add("link", { rel: "manifest", href: "/app/static/manifest.json" });
  add("link", { rel: "apple-touch-icon", href: "/app/static/apple-touch-icon.png" });
  add("meta", { name: "theme-color", content: "#3B5BFD" });
  add("meta", { name: "mobile-web-app-capable", content: "yes" });
  add("meta", { name: "apple-mobile-web-app-capable", content: "yes" });
  add("meta", { name: "apple-mobile-web-app-title", content: "NirKanA" });
})();
""",
    # On phones the menu covers the screen: close it as soon as a page is chosen (Streamlit leaves it open).
    "close_menu": """
(() => {
  if (window.__nkCloseMenu) return;
  window.__nkCloseMenu = true;
  document.addEventListener("click", (event) => {
    if (window.innerWidth > 768 || !event.target.closest('[data-testid="stSidebarNav"] a')) return;
    setTimeout(() => {
      const close = document.querySelector('[data-testid="stSidebarCollapseButton"] button');
      if (close) close.click();
    }, 150);
  }, true);
})();
""",
    # The ticket preview's print button (no onclick="…": inline event handlers are not allowed either).
    "print_button": """
document.getElementById("nk-print").addEventListener("click", () => window.print());
""",
}


def script_tag(script: str, /, **data: str) -> str:
    """The <script> for one of SCRIPTS, with its values as data- attributes (escaped)."""
    attributes = "".join(f' data-{key}="{escape(str(value), quote=True)}"' for key, value in data.items())
    return f"<script{attributes}>{SCRIPTS[script]}</script>"


def source_hash(text: str) -> str:
    """How a Content-Security-Policy names an inline script: the SHA-256 of its exact text."""
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


def streamlit_inline_scripts() -> list[str]:
    """The inline scripts of the installed Streamlit's own page (index.html), which the policy must also allow."""
    import importlib.util
    import re
    from pathlib import Path

    package = Path(importlib.util.find_spec("streamlit").origin).parent  # located, not imported: core stays UI-free
    page = (package / "static" / "index.html").read_text(encoding="utf-8")
    return re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", page, flags=re.S)


def script_src() -> str:
    """The script-src directive for the Caddyfile."""
    hashes = [source_hash(text) for text in [*streamlit_inline_scripts(), *SCRIPTS.values()]]
    return "script-src 'self' " + " ".join(hashes)


if __name__ == "__main__":
    print(script_src())
