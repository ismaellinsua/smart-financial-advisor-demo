"""Remembered sign-ins and the ticket in progress survive a reload; they end when they must."""

from datetime import timedelta

import pytest

from core import clock


@pytest.fixture
def store(make_store):
    s = make_store()
    s.load_preset("retail", with_demo_sales=False)
    s.create_user("Ana", "ana", "admin", "Segura2026!")
    s.create_user("Luis", "luis", "empleado", "583920")
    return s


def _uid(store, username):
    users = store.users()
    return int(users.loc[users["username"] == username, "id"].iloc[0])


def test_a_remembered_sign_in_resumes_and_ends_on_logout(store):
    token = store.create_session(_uid(store, "luis"), "Mozilla/5.0")
    assert store.resume_session(token, 720)["username"] == "luis"
    with store.db.tx() as cur:  # only the fingerprint is stored, never the token
        assert not cur.execute("SELECT 1 FROM sessions WHERE token_hash = ?", (token,)).fetchone()
    assert store.resume_session("otro-token", 720) is None
    store.end_session(token)
    assert store.resume_session(token, 720) is None


def test_sessions_expire_when_idle(store, monkeypatch):
    token = store.create_session(_uid(store, "luis"))
    later = clock.now() + timedelta(minutes=31)
    monkeypatch.setattr(clock, "now", lambda: later)
    assert store.resume_session(token, 30) is None
    monkeypatch.setattr(clock, "now", lambda: later - timedelta(minutes=31))
    assert store.resume_session(token, 30) is None  # an expired session stays ended


def test_a_session_never_outlives_seven_days_however_often_it_is_used(store, monkeypatch):
    from core.store_sessions import SESSION_MAX_AGE

    token = store.create_session(_uid(store, "luis"))
    start = clock.now()
    day = start
    while day - start < SESSION_MAX_AGE - timedelta(days=1):  # used every day, never idle
        day += timedelta(days=1)
        monkeypatch.setattr(clock, "now", lambda d=day: d)
        assert store.resume_session(token, 2 * 24 * 60) is not None
    monkeypatch.setattr(clock, "now", lambda: start + SESSION_MAX_AGE + timedelta(minutes=1))
    assert store.resume_session(token, 2 * 24 * 60) is None  # not idle: too old


CHROME_129 = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.6668.89"
CHROME_130 = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.58"
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0"


def test_a_copied_token_does_not_work_on_another_browser(store):
    token = store.create_session(_uid(store, "luis"), CHROME_129)
    assert store.resume_session(token, 720, CHROME_130)["username"] == "luis"  # the browser updated itself
    assert store.resume_session(token, 720, FIREFOX) is None  # the token taken elsewhere
    assert store.resume_session(token, 720, CHROME_129) is not None  # …without signing the real person out
    assert store.resume_session(token, 720, "") is not None  # unknown browser: nothing to compare


@pytest.mark.parametrize("change", ["admin_reset", "own_change", "deactivated"])
def test_pin_changes_and_deactivation_sign_out_every_device(store, change):
    uid = _uid(store, "luis")
    token = store.create_session(uid)
    if change == "admin_reset":
        store.set_user_secret(uid, "740291", by="ana")
    elif change == "own_change":
        store.change_own_secret(uid, "583920", "740291")
    else:
        store.update_user(uid, active=False, by="ana")
    assert store.resume_session(token, 720) is None
    other = store.create_session(_uid(store, "ana"))
    assert store.resume_session(other, 720) is not None  # other people stay signed in


def test_ticket_in_progress_is_kept_per_person(store):
    luis, ana = _uid(store, "luis"), _uid(store, "ana")
    store.save_cart(luis, {3: 2, 5: 1, 7: 0})
    assert store.saved_cart(luis) == {3: 2, 5: 1}
    assert store.saved_cart(ana) == {}
    store.save_cart(luis, {})
    assert store.saved_cart(luis) == {}
    store.save_cart(luis, {3: 1})
    store.reset()  # products are replaced: a saved ticket would point to the wrong ones
    assert store.saved_cart(luis) == {}


RELOAD = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
import ui.auth
from core.db import Store
ui.auth._cookie_token = lambda: {token!r}
store = Store({db!r})
user = ui.auth.require_user(store, store.settings())
st.markdown("signed in as " + (user["username"] if user else "nobody"))
"""


def test_a_reload_signs_back_in_from_the_cookie(tmp_path):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    from core.db import Store

    db = str(tmp_path / "reload.db")
    store = Store(db)
    store.load_preset("retail", with_demo_sales=False)
    store.create_user("Luis", "luis", "admin", "Segura2026!")
    token = store.create_session(int(store.users()["id"].iloc[0]))
    root = str(Path(__file__).resolve().parent.parent)

    def page(tok):
        at = AppTest.from_string(RELOAD.format(root=root, token=tok, db=db), default_timeout=30).run()
        assert not at.exception, at.exception
        return " ".join(str(m.value) for m in at.markdown)

    assert "signed in as luis" in page(token)
    assert "signed in as nobody" in page("forged")
    store.end_session(token)  # logout
    assert "signed in as nobody" in page(token)
    store.close()


def test_password_reset_by_email(store):
    from core.db import AuthError

    assert store.start_password_reset("ana") is None  # no business email yet
    store.save_settings({"email": "duena@example.com"})
    assert store.start_password_reset("luis") is None  # staff reset their PIN with an administrator
    assert store.start_password_reset("nadie") is None
    code, email = store.start_password_reset("ana")
    assert email == "duena@example.com" and len(code) == 8 and code.isdigit()
    token = store.create_session(_uid(store, "ana"))
    assert not store.finish_password_reset("ana", "00000000" if code != "00000000" else "11111111", "NuevaClave2026!")
    with pytest.raises(ValueError):
        store.finish_password_reset("ana", code, "corta")
    assert store.finish_password_reset("ana", code, "NuevaClave2026!")
    assert not store.finish_password_reset("ana", code, "OtraClave2026!")  # single use
    assert store.resume_session(token, 720) is None  # every device signed out
    assert store.authenticate("ana", "NuevaClave2026!")["username"] == "ana"
    with pytest.raises(AuthError):
        store.authenticate("ana", "Segura2026!")


def test_password_reset_codes_resist_guessing_and_flooding(store, monkeypatch):
    from datetime import timedelta

    import core.store_sessions as sessions

    store.save_settings({"email": "duena@example.com"})
    code, _ = store.start_password_reset("ana")
    wrong = "12345678" if code != "12345678" else "87654321"
    for _ in range(5):
        assert not store.finish_password_reset("ana", wrong, "NuevaClave2026!")
    assert not store.finish_password_reset("ana", code, "NuevaClave2026!")  # locked after 5 wrong tries
    assert store.start_password_reset("ana") and store.start_password_reset("ana")
    assert store.start_password_reset("ana") is None  # at most 3 codes an hour
    later = sessions.clock.now() + timedelta(hours=2)  # a new hour, but already 3 codes today…
    with store.db.tx() as cur:  # …plus three more earlier today: six in the last day
        for _ in range(3):
            cur.execute("INSERT INTO password_resets(user_id, code_hash, created_at, expires_at) "
                        "SELECT user_id, code_hash, ?, expires_at FROM password_resets LIMIT 1",
                        ((later - timedelta(hours=5)).isoformat(timespec="seconds"),))
    monkeypatch.setattr(sessions.clock, "now", lambda: later)
    assert store.start_password_reset("ana") is None  # at most 6 codes a day

def test_two_step_codes_work_once_and_keys_are_encrypted(make_store, monkeypatch):
    import time

    from core.db import AuthError
    from core.secretbox import PREFIX
    from core.security import new_totp_secret, totp_code

    store = make_store()
    admin = store.create_user("Elena", "elena", "admin", "Segura2026")
    plain = new_totp_secret()
    store.enable_two_factor(admin, plain, totp_code(plain))  # no DATA_KEY yet: kept as before
    with store.db.tx() as cur:
        assert cur.execute("SELECT totp_secret FROM users WHERE id = ?", (admin,)).fetchone()["totp_secret"] == plain

    monkeypatch.setenv("DATA_KEY", "una-clave-larga-y-aleatoria-de-prueba-de-32+")
    code = totp_code(plain, time.time() - 30)
    assert store.authenticate("elena", "Segura2026", otp=code)["id"] == admin
    with store.db.tx() as cur:  # encrypted at that sign-in
        stored = cur.execute("SELECT totp_secret FROM users WHERE id = ?", (admin,)).fetchone()["totp_secret"]
    assert stored.startswith(PREFIX) and plain not in stored
    with pytest.raises(AuthError):
        store.authenticate("elena", "Segura2026", otp=code)  # the same code, again: refused
    with pytest.raises(AuthError):
        store.authenticate("elena", "Segura2026", otp=totp_code(plain, time.time() - 60))  # an older one too
    assert store.authenticate("elena", "Segura2026", otp=totp_code(plain))["id"] == admin  # a new one works

    monkeypatch.setenv("DATA_KEY", "otra-clave")  # a different key: the check fails safely, never lets anyone in
    with pytest.raises(AuthError):
        store.authenticate("elena", "Segura2026", otp=totp_code(plain, time.time() + 30))



def test_older_encrypted_keys_are_read_and_upgraded(make_store, monkeypatch):
    """Keys encrypted by the first version (SHA-256-derived) still work and move to the scrypt-derived key."""
    import time

    from core import secretbox
    from core.security import new_totp_secret, totp_code

    monkeypatch.setenv("DATA_KEY", "otra-clave-larga-y-aleatoria-de-prueba-32+")
    store = make_store()
    admin = store.create_user("Elena", "elena", "admin", "Segura2026")
    plain = new_totp_secret()
    legacy = secretbox.LEGACY_PREFIX + secretbox._fernet(secretbox._key(), 1).encrypt(plain.encode()).decode()
    with store.db.tx() as cur:
        cur.execute("UPDATE users SET totp_secret = ? WHERE id = ?", (legacy, admin))
    assert store.authenticate("elena", "Segura2026", otp=totp_code(plain, time.time() - 30))["id"] == admin
    with store.db.tx() as cur:
        stored = cur.execute("SELECT totp_secret FROM users WHERE id = ?", (admin,)).fetchone()["totp_secret"]
    assert stored.startswith(secretbox.PREFIX) and secretbox.unseal(stored) == plain


def test_a_short_data_key_is_reported(monkeypatch, caplog):
    import logging

    from core import logs, secretbox

    logs.setup()
    logging.getLogger(logs.ROOT).propagate = True
    try:
        monkeypatch.setenv("DATA_KEY", "corta")
        with caplog.at_level(logging.WARNING, logger=logs.ROOT):
            sealed = secretbox.seal("JBSWY3DPEHPK3PXP")
        assert "data_key_short" in caplog.text and "corta" not in caplog.text
        assert secretbox.unseal(sealed) == "JBSWY3DPEHPK3PXP"
    finally:
        logging.getLogger(logs.ROOT).propagate = False
