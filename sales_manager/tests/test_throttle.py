"""Slowing down guessing: the counters live in the database, so every server shares them and restarts keep them."""

from core import throttle


def test_two_servers_share_the_same_counters(make_store):
    target = make_store.targets.new()
    one, two = make_store(target), make_store(target)  # two servers on one database
    t0 = 1_800_000_000
    for i in range(throttle.MAX_FAILURES):
        (one if i % 2 else two).throttle_failed("1.2.3.4", now=t0 + i)
    assert one.throttle_blocked_minutes("1.2.3.4", now=t0 + 10) == throttle.FIRST_BLOCK_MINUTES
    assert two.throttle_blocked_minutes("1.2.3.4", now=t0 + 10) == throttle.FIRST_BLOCK_MINUTES
    assert two.throttle_blocked_minutes("5.6.7.8", now=t0 + 10) == 0  # the owner's device is unaffected

    later = t0 + throttle.FIRST_BLOCK_MINUTES * 60 + 20  # blocked again: twice as long
    for i in range(throttle.MAX_FAILURES):
        one.throttle_failed("1.2.3.4", now=later + i)
    assert two.throttle_blocked_minutes("1.2.3.4", now=later + 10) == 2 * throttle.FIRST_BLOCK_MINUTES
    two.throttle_succeeded("1.2.3.4")
    assert one.throttle_blocked_minutes("1.2.3.4", now=later + 10) == 0


def test_addresses_are_stored_hashed_and_forgotten(make_store):
    store = make_store()
    t0 = 1_800_000_000
    store.throttle_failed("9.9.9.9", now=t0)
    with store.db.tx() as cur:
        keys = [r["key"] for r in cur.execute("SELECT key FROM login_throttle").fetchall()]
    assert keys == [throttle.key_hash("9.9.9.9")] and "9.9.9.9" not in keys[0]
    store.throttle_failed("8.8.8.8", now=t0 + throttle.FORGET_AFTER_SECONDS + 60)  # old rows go on the next write
    with store.db.tx() as cur:
        keys = [r["key"] for r in cur.execute("SELECT key FROM login_throttle").fetchall()]
    assert keys == [throttle.key_hash("8.8.8.8")]


def test_old_failures_fall_out_of_the_window():
    fails, until, level = [], 0, 0
    t0 = 1_800_000_000
    for i in range(throttle.MAX_FAILURES - 1):
        fails, until, level = throttle.after_failure(fails, until, level, t0 + i)
    fails, until, level = throttle.after_failure(fails, until, level, t0 + throttle.WINDOW_SECONDS + 60)
    assert until == 0 and len(fails) == 1  # the earlier ones were too long ago to count


def test_backups_never_carry_the_counters(make_store):
    store = make_store()
    store.throttle_failed("1.2.3.4")
    restored = make_store()
    restored.restore(store.backup_bytes())
    with restored.db.tx() as cur:
        assert cur.execute("SELECT COUNT(*) AS n FROM login_throttle").fetchone()["n"] == 0


def test_the_visitor_is_found_behind_our_proxies_and_cannot_be_faked():
    addr = throttle.client_address
    # Render forwards the visitor; Caddy (inside the container) appends Render's private address.
    assert addr("203.0.113.9, 10.0.4.7", "127.0.0.1") == "203.0.113.9"
    assert addr("203.0.113.9, 172.17.0.1", "127.0.0.1") == "203.0.113.9"  # what Caddy really sends (tested)
    # Two visitors are two keys, not one shared counter.
    assert addr("198.51.100.1, 10.0.0.2", "127.0.0.1") != addr("198.51.100.2, 10.0.0.2", "127.0.0.1")
    # Whatever the visitor writes in the header goes to the left and is ignored.
    assert addr("6.6.6.6, 203.0.113.9, 10.0.4.7", "127.0.0.1") == "203.0.113.9"
    assert addr("6.6.6.6, 1.1.1.1, basura, 203.0.113.9, 10.0.4.7", "127.0.0.1") == "203.0.113.9"
    # A proxy of ours with a public address is declared, and skipped too.
    assert addr("203.0.113.9, 192.0.2.50", "10.0.0.1", "192.0.2.0/24") == "203.0.113.9"
    # Straight to the app (locally) or only private hops: the nearest address.
    assert addr("", "127.0.0.1") == "127.0.0.1"
    assert addr("10.1.1.1", "127.0.0.1") == "127.0.0.1"
    assert addr("2001:db8::1, fd00::1", "::1") == "2001:db8::1"
    assert addr("", "") == "local"


def test_failed_authorisations_never_lock_the_manager_and_are_limited(make_store):
    import pytest

    from core.db import AuthError

    store = make_store()
    store.create_user("Marta", "marta", "encargado", "481920")
    t0 = 1_800_000_000
    for i in range(throttle.MAX_FAILURES):
        with pytest.raises(AuthError):
            store.authorize("marta", "000000", now=t0 + i)
    with pytest.raises(AuthError, match="Demasiados intentos"):  # even the right PIN waits now
        store.authorize("marta", "481920", now=t0 + 20)
    assert store.authenticate("marta", "481920")["username"] == "marta"  # her own sign-in still works
    assert store.authorize("marta", "481920", now=t0 + throttle.FIRST_BLOCK_MINUTES * 60 + 30)["username"] == "marta"
