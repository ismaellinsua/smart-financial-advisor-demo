"""Scheduled emails to every business that asked for them: the weekly report on Mondays and new important alerts.

    python ops/notify.py

Environment:
    NOTIFY_DATABASES   one database per line: «name=postgresql://…» (defaults to BACKUP_DATABASES)
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM   the sending account (see core/mailer.py)
Databases that serve several businesses are walked business by business. Without SMTP settings nothing is sent.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sales_manager"))


def main() -> int:
    from core.db import Store
    from core.mailer import Mailer
    from core.notifications import send_due
    from core.tenants import businesses_in

    mailer = Mailer.from_settings()
    if mailer is None:
        print("Envío de emails sin configurar: define SMTP_HOST, SMTP_USER y SMTP_PASSWORD.")
        return 0
    raw = os.environ.get("NOTIFY_DATABASES") or os.environ.get("BACKUP_DATABASES") or ""
    failures = 0
    for line in filter(None, (l.strip() for l in raw.splitlines())):
        name, _, url = line.partition("=")
        for code, schema in businesses_in(url.strip()):
            label = f"{name.strip()}{'-' + code if code else ''}"
            store = Store(url.strip(), schema=schema)
            try:
                sent = send_due(store, mailer)
                print(f"{label}: {', '.join(sent) if sent else 'nada pendiente'}")
            except Exception as exc:  # one business failing must not stop the others
                failures += 1
                print(f"{label}: ERROR {type(exc).__name__}", file=sys.stderr)
            finally:
                store.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
