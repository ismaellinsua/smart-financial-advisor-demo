"""Every setting is listed once in core/config.py and documented in .env.example."""

import re
from pathlib import Path

from core import config

ROOT = Path(__file__).resolve().parents[2]


def test_env_example_is_up_to_date():
    assert (ROOT / ".env.example").read_text() == config.example(), "Regenerate it: python -m core.config"


def test_every_setting_read_in_the_code_is_listed():
    sources = [p for p in (ROOT / "sales_manager").rglob("*.py") if "tests" not in p.parts] + \
        list((ROOT / "ops").rglob("*.py"))
    read = set()
    for path in sources:
        text = path.read_text()
        read |= {m.lower() for m in re.findall(r"os\.environ(?:\.get)?[\[(]\"([A-Z0-9_]+)\"", text)}
        read |= set(re.findall(r"\b(?:setting|config\.value|config\.flag|config\.integer|value)\(\"([a-z_]+)\"", text))
    # The system's own (TZ, PATH, HOME) and GitHub Actions' (GITHUB_RUN_ID…) are not settings of the app.
    unlisted = {name for name in read - set(config.SETTINGS) - {"tz", "path", "home"} if not name.startswith("github_")}
    assert not unlisted, f"Add these to core/config.py: {sorted(unlisted)}"


def test_secrets_never_get_example_values():
    for line in (ROOT / ".env.example").read_text().splitlines():
        if line and not line.startswith("#"):
            name, _, example = line.partition("=")
            assert not (config.SETTINGS[name.lower()].secret and example)


def test_values_come_from_secrets_then_environment_then_default(monkeypatch):
    monkeypatch.delenv("TRIAL_DAYS", raising=False)
    assert config.integer("trial_days") == 30
    monkeypatch.setenv("TRIAL_DAYS", "14")
    assert config.integer("trial_days") == 14
    assert config.integer("trial_days", {"trial_days": "7"}.get) == 7
    monkeypatch.setenv("TRIAL_DAYS", "muchos")
    assert config.integer("trial_days") == 30  # not a number: the default
    monkeypatch.setenv("TRIAL_DAYS", "9999")
    assert config.integer("trial_days", high=365) == 365

    def broken(name):
        raise FileNotFoundError("no secrets file")

    monkeypatch.setenv("MULTI_TENANT", "sí")
    assert config.flag("multi_tenant", broken) is True


def test_log_lines_carry_a_reference_but_no_personal_data(make_store, caplog):
    import logging

    from core import logs, throttle

    logs.setup()
    logging.getLogger(logs.ROOT).propagate = True  # let pytest's capture see the lines
    try:
        store = make_store()
        with caplog.at_level(logging.WARNING, logger=logs.ROOT):
            for i in range(throttle.MAX_FAILURES):
                store.throttle_failed("203.0.113.7", now=1_800_000_000 + i)
        text = caplog.text
        assert "sign_in_blocked" in text and "203.0.113.7" not in text
    finally:
        logging.getLogger(logs.ROOT).propagate = False
