"""Slowing down guessing, per device (browser address) rather than per account: whoever keeps failing waits longer
and longer, while the owner, from their own device, can still sign in.

The policy lives here; where the counters are kept is up to the caller. `Store` and the operator directory keep them
in the database, so every server sees the same counts and a restart does not reset them. `MemoryThrottle` is the
fallback when there is no database at hand. Addresses are stored hashed.
"""

import hashlib
import ipaddress
import json
import threading
import time
from collections import deque

from . import logs

log = logs.get("throttle")

MAX_FAILURES, WINDOW_SECONDS = 8, 15 * 60
FIRST_BLOCK_MINUTES, MAX_BLOCK_MINUTES = 15, 24 * 60
FORGET_AFTER_SECONDS = 2 * 24 * 3600  # rows untouched for this long are deleted


# Where reverse proxies live: private networks (RFC 1918, carrier-grade NAT, IPv6 unique-local), loopback and
# link-local. A visitor never reaches us from one of these.
INTERNAL_NETWORKS = tuple(ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
    "::1/128", "fc00::/7", "fe80::/10"))


def client_address(forwarded: str, peer: str, trusted: str = "") -> str:
    """The visitor's address behind reverse proxies (Render, Caddy…).

    X-Forwarded-For lists the client first and each proxy appends the address it received from, so the right-most
    entries are our own proxies. Walking from the right, private and loopback addresses (and those in `trusted`,
    comma-separated networks) are proxies; the first other address is the visitor. Entries to its left were sent by
    the visitor and could be invented, so they are never used. Without a public address, the nearest one counts.
    """
    networks = list(INTERNAL_NETWORKS)
    for item in str(trusted or "").split(","):
        try:
            networks.append(ipaddress.ip_network(item.strip(), strict=False)) if item.strip() else None
        except ValueError:
            continue

    def is_proxy(address) -> bool:
        return any(address.version == net.version and address in net for net in networks)

    chain = [part.strip() for part in str(forwarded or "").split(",") if part.strip()] + [str(peer or "").strip()]
    nearest = ""
    for raw in reversed(chain):
        try:
            address = ipaddress.ip_address(raw.split("%")[0])
        except ValueError:
            continue  # garbage (or a port we do not expect): skip, never trust it
        nearest = nearest or str(address)
        if not is_proxy(address):
            return str(address)
    return nearest or "local"


def key_hash(key: str) -> str:
    return hashlib.sha256(f"nirkana-throttle:{key}".encode()).hexdigest()[:40]


def blocked_minutes(until: float, now: float) -> int:
    return max(1, round((until - now) / 60)) if until > now else 0


def after_failure(fails: list[float], until: float, level: int, now: float,
                  grow: bool = True) -> tuple[list[float], float, int]:
    """The new (recent failures, blocked until, level) after one more failure at `now`. With `grow`, each new
    block doubles (up to MAX_BLOCK_MINUTES); without it, every block lasts FIRST_BLOCK_MINUTES."""
    fails = [t for t in fails if t >= now - WINDOW_SECONDS] + [now]
    if len(fails) >= MAX_FAILURES:
        minutes = min(FIRST_BLOCK_MINUTES * 2 ** level, MAX_BLOCK_MINUTES) if grow else FIRST_BLOCK_MINUTES
        return [], now + minutes * 60, level + 1
    return fails, until, level


class MemoryThrottle:
    """Counters in this server's memory only."""

    def __init__(self):
        self._entries: dict[str, dict] = {}
        self._lock = threading.Lock()

    def blocked_minutes(self, key: str, now: float | None = None) -> int:
        now = time.time() if now is None else now
        with self._lock:
            entry = self._entries.get(key)
            return blocked_minutes(entry["until"], now) if entry else 0

    def failed(self, key: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            if len(self._entries) > 10_000:  # forget old visitors so memory stays bounded
                for k in [k for k, e in self._entries.items() if e["until"] < now and not e["fails"]]:
                    del self._entries[k]
            entry = self._entries.setdefault(key, {"fails": deque(), "until": 0.0, "level": 0})
            fails, entry["until"], entry["level"] = after_failure(list(entry["fails"]), entry["until"],
                                                                  entry["level"], now)
            entry["fails"] = deque(fails)

    def succeeded(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class ThrottleMixin:
    """The same counters in the business's database (table `login_throttle`). Mixed into `Store`."""

    def throttle_blocked_minutes(self, key: str, now: float | None = None) -> int:
        now = time.time() if now is None else now
        with self.db.tx() as cur:
            row = cur.execute("SELECT blocked_until FROM login_throttle WHERE key = ?", (key_hash(key),)).fetchone()
        return blocked_minutes(int(row["blocked_until"]), now) if row else 0

    def throttle_failed(self, key: str, now: float | None = None, grow: bool = True) -> None:
        """One more failure for `key`; `grow=False` keeps every block at FIRST_BLOCK_MINUTES (see after_failure)."""
        now = time.time() if now is None else now
        hashed = key_hash(key)
        with self.db.tx() as cur:
            cur.execute("DELETE FROM login_throttle WHERE updated < ? AND blocked_until < ?",
                        (int(now - FORGET_AFTER_SECONDS), int(now)))
            row = cur.execute("SELECT fails, blocked_until, level FROM login_throttle WHERE key = ?",
                              (hashed,)).fetchone()
            fails, until, level = (json.loads(row["fails"]), row["blocked_until"], row["level"]) if row else ([], 0, 0)
            fails, until, level = after_failure(fails, until, level, now, grow)
            if until > now and not fails:
                log.warning("sign_in_blocked key=%s minutes=%s", hashed[:12], blocked_minutes(until, now))
            # Whole seconds: plain integers on both engines.
            cur.execute("INSERT INTO login_throttle(key, fails, blocked_until, level, updated) VALUES (?, ?, ?, ?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET fails = excluded.fails, blocked_until = excluded.blocked_until, "
                        "level = excluded.level, updated = excluded.updated",
                        (hashed, json.dumps([int(t) for t in fails]), int(until), level, int(now)))

    def throttle_succeeded(self, key: str) -> None:
        with self.db.tx() as cur:
            cur.execute("DELETE FROM login_throttle WHERE key = ?", (key_hash(key),))
