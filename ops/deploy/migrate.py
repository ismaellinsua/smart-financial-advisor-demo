"""Bring every business's database schema up to date before the app starts (run by start.sh).

With one business per database it migrates that one; in multi-business mode, each active business's schema.
Exits with an error, and the container does not start, if any of them fails.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sales_manager"))

from core import config, logs  # noqa: E402
from core.tenants import migrate_all  # noqa: E402

log = logs.get("migrate")


def main() -> int:
    url = config.value("database_url")
    if not url:
        log.info("migrate skipped=no_database_url")
        return 0
    try:
        done = migrate_all(url)
    except Exception as exc:  # noqa: BLE001 - reported, and the container stops
        log.exception("migrate_failed error=%s", type(exc).__name__)
        return 1
    for code, version in done:
        log.info("migrated business=%s version=%s", code or "(única)", version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
