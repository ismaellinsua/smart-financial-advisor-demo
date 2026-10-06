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
