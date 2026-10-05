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


def test_password_reset_by_email(store, monkeypatch):
    from core.db import AuthError

    assert store.start_password_reset("ana") is None  # no business email yet
    store.save_settings({"email": "duena@example.com"})
    assert store.start_password_reset("luis") is None  # staff reset their PIN with an administrator
    assert store.start_password_reset("nadie") is None
    code, email = store.start_password_reset("ana")
    assert email == "duena@example.com" and len(code) == 6
    token = store.create_session(_uid(store, "ana"))
    assert not store.finish_password_reset("ana", "000000" if code != "000000" else "111111", "NuevaClave2026!")
    with pytest.raises(ValueError):
        store.finish_password_reset("ana", code, "corta")
    assert store.finish_password_reset("ana", code, "NuevaClave2026!")
    assert not store.finish_password_reset("ana", code, "OtraClave2026!")  # single use
    assert store.resume_session(token, 720) is None  # every device signed out
    assert store.authenticate("ana", "NuevaClave2026!")["username"] == "ana"
    with pytest.raises(AuthError):
        store.authenticate("ana", "Segura2026!")


def test_password_reset_codes_resist_guessing_and_flooding(store):
    store.save_settings({"email": "duena@example.com"})
    code, _ = store.start_password_reset("ana")
    wrong = "123456" if code != "123456" else "654321"
    for _ in range(5):
        assert not store.finish_password_reset("ana", wrong, "NuevaClave2026!")
    assert not store.finish_password_reset("ana", code, "NuevaClave2026!")  # locked after 5 wrong tries
    assert store.start_password_reset("ana") and store.start_password_reset("ana")
    assert store.start_password_reset("ana") is None  # at most 3 codes an hour
